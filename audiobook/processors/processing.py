"""Orchestrates the TTS pipeline for a single series: validate, synthesize, and convert."""

import os
import shutil
import traceback
from .tts_processor import TTSProcessor, GarbledAudioError
from ..events import NULL_CONTEXT, EventType, JobCancelled
from ..utils.audio import convert_to_mp3
from ..utils.colors import PURPLE, RED, RESET


class NetworkError(Exception):
    """Raised when the network share appears unreachable, signaling the pipeline to abort."""
    pass


def _is_network_error(exc):
    """Check if an exception looks like a network share connectivity issue."""
    err_str = str(exc)
    # FileNotFoundError on a UNC path suggests network share is unreachable
    if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
        filename = str(getattr(exc, 'filename', '') or '')
        if '\\\\' in filename or '\\\\' in err_str:
            return True
    # Windows-specific network error codes
    if isinstance(exc, OSError) and hasattr(exc, 'winerror') and exc.winerror in (
        53,    # ERROR_BAD_NETPATH
        64,    # ERROR_NETNAME_DELETED
        67,    # ERROR_BAD_NET_NAME
        1231,  # ERROR_NETWORK_UNREACHABLE
    ):
        return True
    # SQLite disk I/O error (DB on network share)
    if 'disk I/O error' in err_str:
        return True
    return False


def _safe_mark_failed(db, raw_path, error):
    """Attempt to mark a chapter as failed, returning False if the DB is unreachable."""
    if not db:
        return True
    try:
        db.mark_failed(raw_path, error)
        return True
    except Exception as db_err:
        print(f"\t{RED}Warning: Could not update DB for {os.path.basename(raw_path)}: {db_err}{RESET}")
        return False


DEV_MAX_CHARS = 1500  # In dev mode, truncate chapters to ~2 TTS chunks
CONVERT_TIMEOUT_S = 600  # ffmpeg WAV->MP3 encode — cap against a hang


def process_chapter(raw_path, series_cfg, output_base, tmp_dir, db=None, dev_mode=False,
                    ctx=NULL_CONTEXT):
    """Process a single chapter through TTS: validate, synthesize, and convert to MP3.

    Args:
        raw_path: Path to the raw chapter .txt file.
        series_cfg: Series configuration dict (with tts_engine, pause, etc. merged in).
        output_base: Base output directory for generated audio.
        tmp_dir: Temporary directory for intermediate WAV chunks.
        db: Optional ChapterDB instance for status tracking.
        dev_mode: When True, truncate chapter to first few lines for faster runs.
        ctx: PipelineContext for event emission and cancellation.
    """
    series_name = series_cfg.get('name', '')
    series_out = os.path.join(output_base, series_name)
    os.makedirs(series_out, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    processor = TTSProcessor(raw_path, series_cfg, output_dir=series_out, tmp_dir=tmp_dir,
                             ctx=ctx)
    fname = os.path.basename(raw_path)
    pretty = os.path.splitext(fname)[0]
    pretty = pretty.split('_', 1)[-1] if '_' in pretty else pretty

    if processor.check_already_exists():
        if db:
            db.mark_done(raw_path)
        ctx.emit(EventType.CHAPTER_SKIPPED, series=series_name, chapter=pretty,
                 raw_path=raw_path)
        return

    print(f"\n\t{PURPLE}{pretty}{RESET}")
    ctx.emit(EventType.CHAPTER_STARTED, series=series_name, chapter=pretty,
             raw_path=raw_path)

    if db:
        db.mark_processing(raw_path, processor.output_path)
    try:
        processor.validate_file(series_cfg.get('replacements', {}))
        if dev_mode and processor.cleaned_file_name:
            with open(processor.cleaned_file_name, 'r', encoding='utf-8') as f:
                text = f.read()
            if len(text) > DEV_MAX_CHARS:
                with open(processor.cleaned_file_name, 'w', encoding='utf-8') as f:
                    f.write(text[:DEV_MAX_CHARS])
        processor.convert_text_to_speech()
        # Encode the merged WAV to MP3 locally, then move only the final file to the
        # output dir (network share). Cancellation checks + a timeout bound the step
        # so a stalled share write can't hang the job the way an in-place convert did.
        ctx.check_cancelled()
        local_mp3 = os.path.join(tmp_dir, f"{processor.base_output_file}.mp3")
        convert_to_mp3(processor.merged_wav_path, local_mp3, timeout=CONVERT_TIMEOUT_S)
        ctx.check_cancelled()
        shutil.move(local_mp3, processor.output_path_mp3)
        if db:
            db.mark_done(raw_path, output_path=processor.output_path_mp3)
        ctx.emit(EventType.CHAPTER_DONE, series=series_name, chapter=pretty,
                 raw_path=raw_path)
    except JobCancelled:
        # Must precede all other handlers: the bare `except Exception` below
        # would otherwise mark a cancelled chapter as failed. Temp chunk WAVs
        # in tmp/ are intentionally kept — they are the resume mechanism.
        if db:
            try:
                db.reset_chapter(raw_path)
            except Exception:
                pass  # worker's reset_all_processing() is the backstop
        raise
    except GarbledAudioError as e:
        ctx.emit(EventType.CHAPTER_FAILED, series=series_name, chapter=pretty,
                 raw_path=raw_path, error=str(e))
        if not _safe_mark_failed(db, raw_path, e):
            raise NetworkError(f"Network share unreachable while recording failure for {fname}") from e
    except NetworkError:
        raise
    except Exception as e:
        print(f"\t{RED}Error on {raw_path}: {e}{RESET}")
        traceback.print_exc()
        ctx.emit(EventType.CHAPTER_FAILED, series=series_name, chapter=pretty,
                 raw_path=raw_path, error=str(e))
        db_ok = _safe_mark_failed(db, raw_path, e)
        if _is_network_error(e) or not db_ok:
            raise NetworkError(f"Network share unreachable: {e}") from e
    finally:
        processor.clean_up()


def process_series(input_dir, series_cfg, output_base, tmp_dir, db=None, dev_mode=False,
                   ctx=NULL_CONTEXT):
    """Process all chapter .txt files in a series directory through the TTS pipeline.

    Args:
        input_dir: Directory containing raw chapter .txt files.
        series_cfg: Series configuration dict from config.yml.
        output_base: Base output directory for generated audio.
        tmp_dir: Temporary directory for intermediate WAV chunks.
        db: Optional ChapterDB instance for status tracking.
        dev_mode: When True, truncate chapters to first few lines for faster runs.
        ctx: PipelineContext for event emission and cancellation.
    """
    series_name = series_cfg.get('name', '')

    # Build the list of chapters to process
    if db:
        actionable = db.get_actionable(series_name)
        chapters = [ch['raw_path'] for ch in actionable]
    else:
        chapters = []
        for root, _, files in os.walk(input_dir):
            for fname in files:
                if fname.endswith('.txt') and not fname.endswith('_cleaned.txt'):
                    chapters.append(os.path.join(root, fname))

    for path in chapters:
        ctx.check_cancelled()
        try:
            process_chapter(path, series_cfg, output_base, tmp_dir, db=db, dev_mode=dev_mode,
                            ctx=ctx)
        except NetworkError:
            print(f"\n\t{RED}Aborting series '{series_name}' — network share unreachable{RESET}")
            raise

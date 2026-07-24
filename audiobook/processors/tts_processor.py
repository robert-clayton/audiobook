"""Core TTS processor: text chunking, speaker resolution, audio generation, and merging."""

import re
import os
import shutil
import wave
import traceback
from tqdm import tqdm

import nltk
from nltk.tokenize import sent_tokenize
from ..events import NULL_CONTEXT, EventType, JobCancelled
from ..validators.validate_file import validate
from ..utils.audio import adjust_volume, change_playback_speed, merge_audio, modulate_audio
from ..utils.colors import RED, YELLOW, GREEN, RESET


class GarbledAudioError(Exception):
    """Raised when TTS produces garbled/abnormally long audio after retries."""


class TTSProcessor:
    """Converts a chapter text file to audio using TTS with speaker-tagged voice cloning."""

    DEFAULT_NARRATOR = 'onyx'

    CHUNK_SIZE_COQUI = 250
    CHUNK_SIZE_QWEN = 750
    MAX_DURATION_PER_CHAR = 0.3  # seconds per character — ~3 chars/sec is extremely slow speech
    MIN_CHUNK_DURATION = 15      # seconds — floor for very short texts
    MAX_CHUNK_RETRIES = 10
    MERGE_TIMEOUT_S = 600        # ffmpeg concat of local chunk WAVs — cap against a hang

    def __init__(self, file_name, config, output_dir, tmp_dir, max_chunk_size=None,
                 ctx=NULL_CONTEXT):
        self._ensure_nltk_data()
        self.ctx = ctx
        self.file_name = file_name
        self.narrator = config.get('narrator', TTSProcessor.DEFAULT_NARRATOR)
        self.cleaned_file_name = None
        if config.get('tts_engine') == 'qwen':
            from .tts_qwen import QwenTTSInstance
            self.tts = QwenTTSInstance()
            default_chunk_size = TTSProcessor.CHUNK_SIZE_QWEN
        else:
            from .tts_instance import TTSInstance
            self.tts = TTSInstance()
            default_chunk_size = TTSProcessor.CHUNK_SIZE_COQUI
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir
        self.max_chunk_size = max_chunk_size or default_chunk_size
        self.speakers = self._load_speakers()
        self.character_speaker_mappings = config.get('mappings', {})
        self.narrators_config = config.get('narrators', {})
        self.system = config.get('system', {})
        self.will_modulate_system = self.system.get('modulate', True)

        self.base_output_file = os.path.splitext(os.path.basename(self.file_name))[0]
        self.output_path = os.path.join(self.output_dir, f"{self.base_output_file}.wav")
        self.output_path_mp3 = os.path.join(self.output_dir, f"{self.base_output_file}.mp3")
        # Merged WAV is written locally (in tmp_dir); only the final MP3 is moved to
        # output_dir, so a large WAV is never written/read over the network share.
        self.merged_wav_path = os.path.join(self.tmp_dir, f"{self.base_output_file}.merged.wav")

    def _get_narrator_setting(self, speaker_name, key, fallback=None):
        """Look up a narrator setting, falling back to 'default' then fallback."""
        narrator_cfg = self.narrators_config.get(speaker_name, {})
        if key in narrator_cfg:
            return narrator_cfg[key]
        default_cfg = self.narrators_config.get('default', {})
        return default_cfg.get(key, fallback)

    def _ensure_nltk_data(self):
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab')

    def _load_speakers(self):
        """Return list of available speaker names from the speakers/ directory."""
        if not os.path.isdir('speakers'):
            raise FileNotFoundError("speakers directory not found.")
        from ..speakers import list_speakers
        return list_speakers()

    def validate_file(self, replacements):
        """Clean and validate the source text file, applying word replacements."""
        if not os.path.isfile(self.file_name):
            print(f"{RED}File '{self.file_name}' not found.{RESET}")
            raise FileNotFoundError(self.file_name)
        self.cleaned_file_name = validate(self.file_name, replacements)

    def check_already_exists(self):
        """Return True if the output WAV or MP3 already exists."""
        return os.path.exists(self.output_path) or os.path.exists(self.output_path_mp3)

    def convert_text_to_speech(self):
        """Parse speaker tags, generate TTS audio per chunk, and merge into a single WAV.

        Chunks are grouped by resolved speaker across all parts so batches stay
        full: an alternating narrator/system chapter would otherwise degrade
        into single-chunk batch calls at every speaker switch. Output order is
        unaffected — the part/chunk-indexed filenames define the merge order.
        """
        temp_files = []
        if self.check_already_exists():
            return

        with open(self.cleaned_file_name, 'r', encoding='utf-8') as f:
            text = f.read()

        parts = re.split(r'(<<SPEAKER=[^>]+>>.*?<</SPEAKER>>)', text, flags=re.DOTALL)
        parts = [p for p in parts if p.strip()]

        # Compute total from actual content (excluding speaker tag markup)
        total_chars = 0
        for p in parts:
            m = re.search(r'<<SPEAKER=[^>]+>>(.+?)<</SPEAKER>>', p, flags=re.DOTALL)
            total_chars += len(m.group(1)) if m else len(p)

        gui_mode = os.environ.get('AUDIOBOOK_GUI') == '1'
        progress = tqdm(total=total_chars, desc=f"{GREEN}Progress{RESET}", unit="char",
                        disable=gui_mode)
        chars_done = 0

        def emit_progress():
            self.ctx.emit(EventType.CHUNK_PROGRESS, chapter=self.base_output_file,
                          raw_path=self.file_name,
                          chars_done=chars_done, chars_total=total_chars)

        # ── Collect chunks in output order, grouping work per resolved speaker ──
        # name -> {'speaker_file', 'pause', 'items': [{'text','path','chars','is_system'}]}
        # is_system is per-item (not per-group): the system voice may also be a
        # regular narrator/mapping voice, and only system parts get modulated.
        groups = {}

        for idx, part in enumerate(parts):
            match = re.search(r'<<SPEAKER=([^>]+)>>(.+?)<</SPEAKER>>', part, flags=re.DOTALL)
            if match:
                name = self.narrator if match.group(1)=='default' else match.group(1).lower()
                content = match.group(2)
            else:
                name, content = self.narrator, part

            is_system = (name == 'system')
            if is_system:
                name = self.system.get('voice', TTSProcessor.DEFAULT_NARRATOR)

            if name not in self.speakers and name in self.character_speaker_mappings:
                name = self.character_speaker_mappings[name]

            speaker_file = os.path.join('speakers', f"{name}.wav")

            for cidx, chunk in enumerate(self._split_text(content)):
                if not chunk.strip():
                    chars_done += len(chunk)
                    progress.update(len(chunk))
                    continue

                out_wave_name = f'{self.base_output_file}_part{idx}_{name}_{cidx}.wav'
                out_wav_path = os.path.join(self.tmp_dir, out_wave_name)
                temp_files.append(out_wav_path)
                if os.path.exists(out_wav_path):
                    # Resume: chunk already generated (and post-processed) earlier
                    chars_done += len(chunk)
                    progress.update(len(chunk))
                    continue

                group = groups.setdefault(name, {
                    'speaker_file': speaker_file,
                    'pause': self._get_narrator_setting(name, 'pause'),
                    'items': [],
                })
                group['items'].append({
                    'text': chunk.strip('<>').strip(),
                    'path': out_wav_path,
                    'chars': len(chunk),
                    'is_system': is_system,
                })

        # ── Generate per speaker: full batches instead of per-part fragments ──
        batch_size = 5
        for name, group in groups.items():
            self.ctx.check_cancelled()
            speaker_file = group['speaker_file']
            pause = group['pause']
            # Similar-length chunks batch together: a batch decodes until its
            # longest member finishes, so homogeneous batches waste less time.
            items = sorted(group['items'], key=lambda it: len(it['text']))

            try:
                if hasattr(self.tts, 'tts_batch_to_files'):
                    for i in range(0, len(items), batch_size):
                        self.ctx.check_cancelled()
                        batch = items[i:i + batch_size]
                        self.tts.tts_batch_to_files(
                            texts=[it['text'] for it in batch], speaker_wav=speaker_file,
                            file_paths=[it['path'] for it in batch], language="en", pause=pause)
                        done = sum(it['chars'] for it in batch)
                        chars_done += done
                        progress.update(done)
                        emit_progress()
                else:
                    for it in items:
                        self.ctx.check_cancelled()
                        self.tts.tts_to_file(text=it['text'], speaker_wav=speaker_file,
                                             file_path=it['path'], language="en", pause=pause)
                        chars_done += it['chars']
                        progress.update(it['chars'])
                        emit_progress()
            except JobCancelled:
                # Re-raise before the generic handler below can swallow it
                progress.close()
                raise
            except Exception as e:
                progress.write(f"\t{RED}Error on TTS: {e}{RESET}")
                traceback.print_exc()
                # Remove paths for chunks that failed; continue with other speakers
                missing = {it['path'] for it in items if not os.path.exists(it['path'])}
                temp_files = [f for f in temp_files if f not in missing]
                continue

            # Validate chunk durations — retry abnormally long ones
            failed_text = self._validate_chunk_durations(
                [it['text'] for it in items], [it['path'] for it in items],
                speaker_file, pause)
            if failed_text:
                preview = failed_text[:200] + ("..." if len(failed_text) > 200 else "")
                progress.close()
                msg = (
                    f"TTS produced garbled audio after {self.MAX_CHUNK_RETRIES} retries. "
                    f"Problem text: {preview}"
                )
                print(
                    f"\t{RED}Skipping chapter '{self.base_output_file}' — "
                    f"TTS produced garbled audio after {self.MAX_CHUNK_RETRIES} retries.{RESET}\n"
                    f"\t{YELLOW}Problem text: {preview}{RESET}")
                for f in temp_files:
                    if os.path.exists(f):
                        os.remove(f)
                raise GarbledAudioError(msg)

            # Post-process chunks (system modulation + per-narrator volume)
            volume = self._get_narrator_setting(name, 'volume')
            for it in items:
                if not os.path.exists(it['path']):
                    continue
                if it['is_system']:
                    if self.will_modulate_system:
                        modulate_audio(it['path'], self.tmp_dir)
                    if self.system.get('speed', 1.0) != 1.0:
                        change_playback_speed(it['path'], self.system['speed'])
                if volume is not None and volume != 1.0:
                    adjust_volume(it['path'], volume)
        progress.close()

        self.ctx.check_cancelled()
        # Merge into the local tmp WAV; process_chapter encodes it to MP3 locally
        # and moves only that final file to the (network) output dir.
        if len(temp_files) > 1 and merge_audio(temp_files, self.merged_wav_path,
                                               timeout=self.MERGE_TIMEOUT_S):
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            shutil.move(temp_files[0], self.merged_wav_path)
        print(f"\t{GREEN}Saved!{RESET}")

    def _split_text(self, text):
      """Split text into chunks up to max_chunk_size, breaking on sentence boundaries."""
      sentences = sent_tokenize(text)
      chunks = []
      buffer = ""
      separator = "\n\n"

      for sentence in sentences:
          sentence = sentence.strip()
          if not sentence:
              continue

          # If the sentence itself is longer than max_chunk_size, hard-split it
          if len(sentence) > self.max_chunk_size:
              if buffer:
                  chunks.append(buffer.strip())
                  buffer = ""
              words = sentence.split()
              word_buf = ""
              for word in words:
                  if len(word_buf) + len(word) + 1 > self.max_chunk_size:
                      chunks.append(word_buf.strip())
                      word_buf = ""
                  word_buf += word + " "
              if word_buf:
                  chunks.append(word_buf.strip())
              continue

          # Would adding this sentence exceed the limit?
          if buffer and len(buffer) + len(separator) + len(sentence) > self.max_chunk_size:
              chunks.append(buffer.strip())
              buffer = sentence
          else:
              buffer = buffer + separator + sentence if buffer else sentence

      if buffer:
          chunks.append(buffer.strip())

      return chunks


    def _get_wav_duration(self, path):
        """Return the duration of a WAV file in seconds, or 0 on error."""
        try:
            with wave.open(path, 'r') as w:
                return w.getnframes() / w.getframerate()
        except Exception:
            return 0

    def _max_duration_for_text(self, text):
        """Return the maximum plausible audio duration for a chunk of text."""
        return max(self.MIN_CHUNK_DURATION, len(text) * self.MAX_DURATION_PER_CHAR)

    def _validate_chunk_durations(self, pending_texts, pending_paths, speaker_file, pause):
        """Retry chunks whose audio is abnormally long (model hallucination).
        Returns the failed text on first unrecoverable failure, or None if all OK."""
        for text, path in zip(pending_texts, pending_paths):
            if not os.path.exists(path):
                continue
            duration = self._get_wav_duration(path)
            max_dur = self._max_duration_for_text(text)
            if duration <= max_dur:
                continue

            ok = False
            for attempt in range(1, self.MAX_CHUNK_RETRIES + 1):
                tqdm.write(
                    f"\t{YELLOW}Chunk too long ({duration:.1f}s, expected <{max_dur:.0f}s), "
                    f"retrying ({attempt}/{self.MAX_CHUNK_RETRIES})...{RESET}")
                os.remove(path)
                try:
                    self.tts.tts_to_file(
                        text=text, speaker_wav=speaker_file,
                        file_path=path, language="en", pause=pause)
                except Exception:
                    break
                duration = self._get_wav_duration(path)
                if duration <= max_dur:
                    ok = True
                    break

            if not ok:
                if os.path.exists(path):
                    os.remove(path)
                return text
        return None

    def clean_up(self):
        """Remove the temporary cleaned text file if it exists."""
        if self.cleaned_file_name and os.path.exists(self.cleaned_file_name):
            os.remove(self.cleaned_file_name)
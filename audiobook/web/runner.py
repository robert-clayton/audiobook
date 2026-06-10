"""GUI facade over the job queue: submits pipeline operations as jobs."""

import os
import threading
from enum import Enum

from ..config import load_config, save_config
from ..state import ChapterDB
from .gui_log import setup_gui_logging
from .jobs import Job, JobQueue, JobStatus, JobType, SCRAPE_TYPES, unload_tts
from .log_capture import install


class PipelineState(Enum):
    IDLE = "Idle"
    SCRAPING = "Scraping"
    GENERATING = "Generating"
    FINISHED = "Finished"
    ERROR = "Error"
    CANCELLED = "Cancelled"


class PipelineRunner:
    """Facade the GUI talks to. All pipeline work runs as queued jobs."""

    def __init__(self, dev_mode=False):
        self.dev_mode = dev_mode
        self._log_capture, self._log_buffer = install()
        setup_gui_logging(self._log_buffer)
        self._config_file = 'config_dev.yml' if dev_mode else 'config.yml'
        self._config = load_config(self._config_file)
        self._db_path = os.path.join(
            self._config['config']['output_dir'], 'audiobook.db'
        )
        self._config_lock = threading.Lock()
        self.queue = JobQueue(
            config_file=self._config_file,
            db_path=self._db_path,
            on_config=self._set_config,
            on_worker_start=self._on_worker_start,
            config_lock=self._config_lock,
        )

    def _set_config(self, config):
        self._config = config

    def _on_worker_start(self):
        self._log_capture.set_capture_thread(threading.current_thread().ident)

    # ── Status (derived from queue state) ────────────────────

    @property
    def is_running(self):
        return self.queue.is_running

    @property
    def is_busy(self):
        return self.queue.is_busy

    @property
    def state(self):
        snap = self.queue.snapshot()
        current = snap['current']
        if current:
            job_type = JobType(current['type'])
            if job_type in SCRAPE_TYPES:
                return PipelineState.SCRAPING
            if job_type == JobType.FULL_PIPELINE:
                if current['progress'].get('phase') == 'scrape':
                    return PipelineState.SCRAPING
                return PipelineState.GENERATING
            return PipelineState.GENERATING
        if snap['history']:
            last = snap['history'][0]
            return {
                JobStatus.DONE.value: PipelineState.FINISHED,
                JobStatus.FAILED.value: PipelineState.ERROR,
                JobStatus.CANCELLED.value: PipelineState.CANCELLED,
            }.get(last['status'], PipelineState.IDLE)
        return PipelineState.IDLE

    @property
    def error_msg(self):
        snap = self.queue.snapshot()
        if not snap['current'] and snap['history']:
            last = snap['history'][0]
            if last['status'] == JobStatus.FAILED.value:
                return last['error']
        return ""

    # ── Queue access ─────────────────────────────────────────

    def queue_snapshot(self):
        return self.queue.snapshot()

    def cancel(self, job_id):
        return self.queue.cancel(job_id)

    def get_events_since(self, seq):
        return self.queue.events_since(seq)

    # ── DB / config / log access for the GUI thread ──────────

    def get_db(self):
        """Create a new DB connection for the GUI thread (read-only queries)."""
        return ChapterDB(self._db_path)

    def get_config(self):
        """Return the current config dict."""
        return self._config

    def update_config(self, mutator):
        """Atomically load, mutate, and save the config file.

        The lock is shared with the job worker's 'latest'-cursor merge-back,
        so GUI edits and a running job can never clobber each other.
        """
        with self._config_lock:
            config = load_config(self._config_file)
            mutator(config)
            save_config(self._config_file, config)
            self._config = config
        return config

    def get_log_since(self, seq):
        """Return (lines, new_seq) for log entries newer than seq.

        Pass seq=0 on page init to receive the full history plus the cursor.
        """
        return self._log_buffer.since(seq)

    def clear_log(self):
        self._log_buffer.clear()

    # ── Maintenance operations (run on GUI io_bound threads) ─

    def sync_all(self):
        """Sync DB with filesystem for all enabled series."""
        from ..pipeline import detect_source_name
        try:
            db = ChapterDB(self._db_path)
        except Exception:
            return
        try:
            out = self._config['config']['output_dir']
            for series in self._config.get('series', []):
                if not series.get('enabled', True):
                    continue
                name = series.get('name', '')
                url = series.get('url', '')
                db.upsert_series(
                    name,
                    url=url,
                    source=detect_source_name(url),
                    narrator=series.get('narrator'),
                    latest_url=series.get('latest'),
                )
                raws_dir = os.path.join(out, name, 'raws')
                series_out = os.path.join(out, name)
                db.sync_filesystem(name, raws_dir, series_out)
        finally:
            db.close()

    def shutdown(self):
        """Clean up on exit: drain the queue, then reset stale chapters."""
        self.queue.shutdown(timeout=10)
        unload_tts()
        try:
            db = ChapterDB(self._db_path)
        except Exception:
            return
        try:
            count = db.reset_all_processing()
            if count:
                print(f"[shutdown] Reset {count} processing chapter(s) to pending")
        finally:
            db.close()

    # ── Job submission (same method names as before) ─────────

    def start_full(self):
        """Queue scrape + generate for all series."""
        def fn(config, db, ctx):
            from ..pipeline import run_scrape_phase, run_audio_phase, print_summary
            run_scrape_phase(config, db, ctx=ctx)
            run_audio_phase(config, db, dev_mode=self.dev_mode, ctx=ctx)
            print_summary(config, db)
        return self.queue.submit(Job(type=JobType.FULL_PIPELINE, fn=fn))

    def start_scrape_only(self):
        """Queue the scraping phase for all series."""
        def fn(config, db, ctx):
            from ..pipeline import run_scrape_phase
            run_scrape_phase(config, db, ctx=ctx)
        return self.queue.submit(Job(type=JobType.SCRAPE_ALL, fn=fn))

    def start_scrape_series(self, series_name):
        """Queue a scrape of a single series."""
        def fn(config, db, ctx):
            from ..pipeline import run_scrape_single_series
            run_scrape_single_series(config, db, series_name, ctx=ctx)
        return self.queue.submit(Job(type=JobType.SCRAPE_SERIES, series=series_name, fn=fn))

    def start_generate_series(self, series_name):
        """Queue audio generation for a single series."""
        def fn(config, db, ctx):
            from ..pipeline import run_audio_single_series
            run_audio_single_series(config, db, series_name, dev_mode=self.dev_mode, ctx=ctx)
        return self.queue.submit(Job(type=JobType.GENERATE_SERIES, series=series_name, fn=fn))

    def start_regenerate_chapter(self, series_name, chapter_id, chapter_title=None):
        """Queue a delete-and-regenerate of a single chapter."""
        def fn(config, db, ctx):
            from ..pipeline import regenerate_chapter
            regenerate_chapter(config, db, series_name, chapter_id,
                               dev_mode=self.dev_mode, ctx=ctx)
        return self.queue.submit(Job(
            type=JobType.REGENERATE_CHAPTER, series=series_name,
            chapter_id=chapter_id, chapter_title=chapter_title, fn=fn))

    def start_rescrape_chapter(self, series_name, chapter_id, chapter_title=None):
        """Queue a re-fetch of chapter text from source."""
        def fn(config, db, ctx):
            from ..pipeline import rescrape_chapter
            rescrape_chapter(config, db, series_name, chapter_id, ctx=ctx)
        return self.queue.submit(Job(
            type=JobType.RESCRAPE_CHAPTER, series=series_name,
            chapter_id=chapter_id, chapter_title=chapter_title, fn=fn))

"""Background thread wrapper for pipeline execution in the GUI."""

import os
import threading
from enum import Enum

from ..config import load_config, save_config
from ..state import ChapterDB
from .log_capture import install


class PipelineState(Enum):
    IDLE = "Idle"
    SCRAPING = "Scraping"
    GENERATING = "Generating"
    FINISHED = "Finished"
    ERROR = "Error"


class PipelineRunner:
    """Manages pipeline execution in a background thread for the GUI."""

    def __init__(self, dev_mode=False):
        self.dev_mode = dev_mode
        self.state = PipelineState.IDLE
        self.error_msg = ""
        self._thread = None
        self._log_capture = install()
        self._config_file = 'config_dev.yml' if dev_mode else 'config.yml'
        self._config = load_config(self._config_file)
        self._db_path = os.path.join(
            self._config['config']['output_dir'], 'audiobook.db'
        )
        self._startup_sync()

    def _startup_sync(self):
        """Sync DB with filesystem on startup so the dashboard is accurate."""
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

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def get_db(self):
        """Create a new DB connection for the GUI thread (read-only queries)."""
        return ChapterDB(self._db_path)

    def get_config(self):
        """Return the current config dict."""
        return self._config

    def get_log_lines(self):
        """Return captured log lines (drains buffer)."""
        return self._log_capture.get_lines()

    def get_log_history(self):
        """Return full log history (non-draining, for page init)."""
        return self._log_capture.get_history()

    def clear_log(self):
        self._log_capture.clear()

    # ── Thread infrastructure ────────────────────────────────

    def _start_thread(self, target):
        self.state = PipelineState.IDLE
        self.error_msg = ""
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        self._log_capture.set_capture_thread(self._thread.ident)

    def _run_with_db(self, fn):
        """Generic wrapper: set env, reload config, open DB, run fn, save config."""
        os.environ['AUDIOBOOK_GUI'] = '1'
        self._config = load_config(self._config_file)
        db = ChapterDB(self._db_path)
        try:
            fn(self._config, db)
            self.state = PipelineState.FINISHED
        except Exception as e:
            self.state = PipelineState.ERROR
            self.error_msg = str(e)
        finally:
            save_config(self._config_file, self._config)
            db.close()
            os.environ.pop('AUDIOBOOK_GUI', None)
            self._unload_tts()

    @staticmethod
    def _unload_tts():
        """Unload TTS model from GPU if loaded."""
        try:
            from ..processors.tts_qwen import QwenTTSInstance
            QwenTTSInstance.unload()
        except Exception:
            pass
        try:
            from ..processors.tts_instance import TTSInstance
            TTSInstance.unload()
        except Exception:
            pass

    # ── Full pipeline ────────────────────────────────────────

    def start_full(self):
        """Run scrape + generate for all series in a daemon thread."""
        if self.is_running:
            return
        self._start_thread(self._run_full)

    def _run_full(self):
        def fn(config, db):
            from ..pipeline import run_scrape_phase, run_audio_phase, print_summary
            self.state = PipelineState.SCRAPING
            run_scrape_phase(config, db)
            self.state = PipelineState.GENERATING
            run_audio_phase(config, db, dev_mode=self.dev_mode)
            print_summary(config, db)
        self._run_with_db(fn)

    # ── Scrape all ───────────────────────────────────────────

    def start_scrape_only(self):
        """Run scraping phase for all series."""
        if self.is_running:
            return
        self._start_thread(self._run_scrape)

    def _run_scrape(self):
        def fn(config, db):
            from ..pipeline import run_scrape_phase
            self.state = PipelineState.SCRAPING
            run_scrape_phase(config, db)
        self._run_with_db(fn)

    # ── Per-series scrape ────────────────────────────────────

    def start_scrape_series(self, series_name):
        """Scrape a single series."""
        if self.is_running:
            return
        self._start_thread(lambda: self._run_scrape_series(series_name))

    def _run_scrape_series(self, series_name):
        def fn(config, db):
            from ..pipeline import run_scrape_single_series
            self.state = PipelineState.SCRAPING
            run_scrape_single_series(config, db, series_name)
        self._run_with_db(fn)

    # ── Per-series generate ──────────────────────────────────

    def start_generate_series(self, series_name):
        """Generate audio for a single series."""
        if self.is_running:
            return
        self._start_thread(lambda: self._run_generate_series(series_name))

    def _run_generate_series(self, series_name):
        def fn(config, db):
            from ..pipeline import run_audio_single_series
            self.state = PipelineState.GENERATING
            run_audio_single_series(config, db, series_name, dev_mode=self.dev_mode)
        self._run_with_db(fn)

    # ── Per-chapter regenerate ───────────────────────────────

    def start_regenerate_chapter(self, series_name, chapter_id):
        """Delete output and re-run TTS for a single chapter."""
        if self.is_running:
            return
        self._start_thread(lambda: self._run_regenerate_chapter(series_name, chapter_id))

    def _run_regenerate_chapter(self, series_name, chapter_id):
        def fn(config, db):
            from ..pipeline import regenerate_chapter
            self.state = PipelineState.GENERATING
            regenerate_chapter(config, db, series_name, chapter_id, dev_mode=self.dev_mode)
        self._run_with_db(fn)

    # ── Per-chapter rescrape ─────────────────────────────────

    def start_rescrape_chapter(self, series_name, chapter_id):
        """Re-fetch chapter text from source and reset for processing."""
        if self.is_running:
            return
        self._start_thread(lambda: self._run_rescrape_chapter(series_name, chapter_id))

    def _run_rescrape_chapter(self, series_name, chapter_id):
        def fn(config, db):
            from ..pipeline import rescrape_chapter
            self.state = PipelineState.SCRAPING
            rescrape_chapter(config, db, series_name, chapter_id)
        self._run_with_db(fn)

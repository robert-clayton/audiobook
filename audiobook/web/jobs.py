"""In-memory FIFO job queue executing pipeline operations on a single worker thread.

Replaces the old one-shot PipelineRunner threading: operations are queued
instead of rejected, a running job can be cancelled cooperatively, and the
GUI observes everything through locked snapshots and a seq-numbered event
ring buffer (safe for any number of browser tabs).
"""

import logging
import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from ..config import load_config, save_config
from ..events import EventType, JobCancelled, PipelineContext
from ..state import ChapterDB

logger = logging.getLogger('audiobook')


class JobType(Enum):
    FULL_PIPELINE = 'full_pipeline'
    SCRAPE_ALL = 'scrape_all'
    SCRAPE_SERIES = 'scrape_series'
    GENERATE_SERIES = 'generate_series'
    REGENERATE_CHAPTER = 'regenerate_chapter'
    RESCRAPE_CHAPTER = 'rescrape_chapter'


JOB_TYPE_LABELS = {
    JobType.FULL_PIPELINE: 'Full Pipeline',
    JobType.SCRAPE_ALL: 'Scrape All',
    JobType.SCRAPE_SERIES: 'Scrape',
    JobType.GENERATE_SERIES: 'Generate',
    JobType.REGENERATE_CHAPTER: 'Regenerate',
    JobType.RESCRAPE_CHAPTER: 'Rescrape',
}

# Job types whose work is scraping (for the SCRAPING/GENERATING state badge)
SCRAPE_TYPES = {JobType.SCRAPE_ALL, JobType.SCRAPE_SERIES, JobType.RESCRAPE_CHAPTER}


class JobStatus(Enum):
    QUEUED = 'queued'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class Job:
    type: JobType
    fn: object                      # fn(config, db, ctx)
    series: str | None = None
    chapter_id: int | None = None
    chapter_title: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str = ""
    progress: dict = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def label(self):
        base = JOB_TYPE_LABELS.get(self.type, self.type.value)
        target = self.chapter_title or self.series
        return f'{base} — {target}' if target else base

    def dedupe_key(self):
        return (self.type, self.series, self.chapter_id)

    def snapshot(self):
        return {
            'id': self.id,
            'type': self.type.value,
            'label': self.label(),
            'series': self.series,
            'chapter_id': self.chapter_id,
            'chapter_title': self.chapter_title,
            'status': self.status.value,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'error': self.error,
            'progress': dict(self.progress),
        }


def unload_tts():
    """Unload whichever TTS singleton is loaded, freeing GPU memory."""
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


class JobQueue:
    """FIFO queue with one daemon worker thread.

    A deque + Condition (rather than queue.Queue) so queued jobs can be
    removed mid-queue on cancel.
    """

    def __init__(self, config_file, db_path, on_config=None, on_worker_start=None,
                 config_lock=None, history_len=20, event_buffer_len=1000):
        self._config_file = config_file
        self._db_path = db_path
        self._on_config = on_config            # callback(config) after each job's reload
        self._on_worker_start = on_worker_start
        self._config_lock = config_lock or threading.Lock()
        self._cond = threading.Condition()
        self._pending = deque()
        self._shutdown = False
        self.current = None
        self.history = deque(maxlen=history_len)
        self._events = deque(maxlen=event_buffer_len)
        self._event_seq = 0
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name='job-queue-worker')
        self._worker.start()

    # ── Public API (any thread) ──────────────────────────────

    def submit(self, job):
        """Enqueue a job. Returns (job, created); when an identical
        (type, series, chapter_id) job is already queued or running, the
        existing job is returned with created=False."""
        with self._cond:
            if self._shutdown:
                return job, False
            key = job.dedupe_key()
            if self.current and self.current.dedupe_key() == key:
                return self.current, False
            for queued in self._pending:
                if queued.dedupe_key() == key:
                    return queued, False
            self._pending.append(job)
            self._cond.notify()
        logger.info(f'[queue] queued: {job.label()} ({job.id})')
        return job, True

    def cancel(self, job_id):
        """Cancel a job. Queued jobs are removed; the running job gets its
        cancel event set (cooperative — takes effect at the next checkpoint)."""
        with self._cond:
            if self.current and self.current.id == job_id:
                self.current.cancel_event.set()
                logger.info(f'[queue] cancelling running job {job_id}...')
                return True
            for job in list(self._pending):
                if job.id == job_id:
                    self._pending.remove(job)
                    job.status = JobStatus.CANCELLED
                    job.finished_at = time.time()
                    self.history.appendleft(job)
                    logger.info(f'[queue] removed queued job: {job.label()} ({job_id})')
                    return True
        return False

    def snapshot(self):
        with self._cond:
            return {
                'current': self.current.snapshot() if self.current else None,
                'queued': [j.snapshot() for j in self._pending],
                'history': [j.snapshot() for j in self.history],
            }

    @property
    def is_running(self):
        with self._cond:
            return self.current is not None

    @property
    def is_busy(self):
        with self._cond:
            return self.current is not None or bool(self._pending)

    def events_since(self, seq):
        """Return (events, new_seq) for events newer than seq."""
        with self._cond:
            events = [ev for s, ev in self._events if s > seq]
            return events, self._event_seq

    def shutdown(self, timeout=10):
        """Cancel everything and wait briefly for the worker to stop."""
        with self._cond:
            self._shutdown = True
            for job in self._pending:
                job.status = JobStatus.CANCELLED
                job.finished_at = time.time()
                self.history.appendleft(job)
            self._pending.clear()
            if self.current:
                self.current.cancel_event.set()
            self._cond.notify()
        self._worker.join(timeout)

    # ── Worker internals ─────────────────────────────────────

    def _append_event(self, event):
        with self._cond:
            self._event_seq += 1
            self._events.append((self._event_seq, event))

    def _on_event(self, job, ev):
        """Event sink: record the event and fold it into the job's progress."""
        self._append_event(ev)
        p = job.progress
        if ev.type == EventType.PHASE_STARTED:
            p['phase'] = ev.message
        elif ev.type == EventType.SERIES_STARTED:
            p['series'] = ev.series
            p['series_idx'] = ev.index
            p['series_total'] = ev.total
            p.pop('chapter', None)
            p.pop('pct', None)
        elif ev.type == EventType.CHAPTER_STARTED:
            p['chapter'] = ev.chapter
            p['raw_path'] = ev.raw_path
            p['pct'] = 0
        elif ev.type == EventType.CHUNK_PROGRESS:
            if ev.chars_total:
                p['pct'] = ev.chars_done * 100 // ev.chars_total
        elif ev.type in (EventType.CHAPTER_DONE, EventType.CHAPTER_FAILED):
            p['pct'] = 100 if ev.type == EventType.CHAPTER_DONE else p.get('pct')

    def _worker_loop(self):
        if self._on_worker_start:
            try:
                self._on_worker_start()
            except Exception:
                pass
        while True:
            with self._cond:
                while not self._pending and not self._shutdown:
                    self._cond.wait()
                if self._shutdown:
                    return
                job = self._pending.popleft()
                self.current = job
            try:
                self._run_job(job)
            except Exception:
                # _run_job handles job errors; this guards the worker itself
                traceback.print_exc()
            finally:
                with self._cond:
                    self.current = None
                    self.history.appendleft(job)
                    drained = not self._pending
                if drained:
                    unload_tts()

    def _run_job(self, job):
        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        ctx = PipelineContext(sink=lambda ev: self._on_event(job, ev),
                              cancel_event=job.cancel_event, job_id=job.id)
        ctx.emit(EventType.JOB_STARTED, message=job.label())
        logger.info(f'[queue] started: {job.label()} ({job.id})')

        db = None
        config = None
        latest_before = {}
        try:
            # config.yml is live state — reload fresh for every job
            with self._config_lock:
                config = load_config(self._config_file)
            latest_before = self._latest_map(config)
            if self._on_config:
                self._on_config(config)
            db = ChapterDB(self._db_path)
            job.fn(config, db, ctx)
            job.status = JobStatus.DONE
            ctx.emit(EventType.JOB_FINISHED, message=job.label())
            logger.info(f'[queue] finished: {job.label()} ({job.id})')
        except JobCancelled:
            job.status = JobStatus.CANCELLED
            ctx.emit(EventType.JOB_CANCELLED, message=job.label())
            logger.info(f'[queue] cancelled: {job.label()} ({job.id})')
            if db:
                try:
                    db.reset_all_processing()
                except Exception:
                    pass
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            ctx.emit(EventType.JOB_FAILED, message=job.label(), error=str(e))
            logger.error(f'[queue] failed: {job.label()} ({job.id}): {e}')
            traceback.print_exc()
        finally:
            job.finished_at = time.time()
            if db:
                # Scraper may have advanced 'latest' cursors even on cancel/failure.
                # Merge only those back into a fresh load so concurrent GUI config
                # edits made during the job are not clobbered.
                try:
                    self._save_latest_cursors(config, latest_before)
                except Exception as e:
                    logger.error(f'[queue] could not save config: {e}')
                try:
                    db.close()
                except Exception:
                    pass

    @staticmethod
    def _latest_map(config):
        return {s.get('name'): s.get('latest') for s in config.get('series', [])}

    def _save_latest_cursors(self, config, latest_before):
        """Write back 'latest' values the job changed, merged into a fresh config."""
        changed = {
            name: latest for name, latest in self._latest_map(config).items()
            if latest_before.get(name) != latest
        }
        with self._config_lock:
            fresh = load_config(self._config_file)
            for series in fresh.get('series', []):
                if series.get('name') in changed:
                    series['latest'] = changed[series['name']]
            save_config(self._config_file, fresh)
        if self._on_config:
            self._on_config(fresh)

"""Structured pipeline events and cooperative cancellation.

Pipeline code emits events through a PipelineContext instead of printing
GUI-targeted output. The CLI passes no context (NULL_CONTEXT), making all
emits no-ops and cancellation impossible — CLI behavior is unchanged.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum


class JobCancelled(Exception):
    """Raised inside pipeline code when the active job's cancel event is set."""


class EventType(str, Enum):
    JOB_STARTED = "job_started"
    JOB_FINISHED = "job_finished"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    PHASE_STARTED = "phase_started"          # message: 'scrape' | 'audio'
    SERIES_STARTED = "series_started"        # index/total for [i/n] display
    SERIES_FINISHED = "series_finished"
    CHAPTER_STARTED = "chapter_started"
    CHUNK_PROGRESS = "chunk_progress"        # chars_done/chars_total
    CHAPTER_DONE = "chapter_done"
    CHAPTER_FAILED = "chapter_failed"
    CHAPTER_SKIPPED = "chapter_skipped"
    LOG = "log"


@dataclass(frozen=True)
class PipelineEvent:
    type: EventType
    ts: float = field(default_factory=time.time)
    job_id: str | None = None
    series: str | None = None
    chapter: str | None = None      # pretty title
    raw_path: str | None = None
    chars_done: int = 0             # content chars only, speaker-tag markup excluded
    chars_total: int = 0
    index: int = 0
    total: int = 0
    message: str = ""
    error: str | None = None


class PipelineContext:
    """Carries the event sink and cancel signal through the pipeline call chain.

    Passed explicitly (``ctx=NULL_CONTEXT`` default) so every existing call
    site — including the CLI — works unchanged.
    """

    def __init__(self, sink=None, cancel_event=None, job_id=None):
        self._sink = sink
        self.cancel_event = cancel_event or threading.Event()
        self.job_id = job_id

    def emit(self, type, **fields):
        if self._sink is None:
            return
        self._sink(PipelineEvent(type=type, job_id=self.job_id, **fields))

    def cancelled(self):
        return self.cancel_event.is_set()

    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise JobCancelled()


NULL_CONTEXT = PipelineContext()

"""Sequence-numbered log buffer and logging bridge for the GUI.

A single GuiLogBuffer is shared by the stdout/stderr capture (legacy print
output) and a logging.Handler on the named 'audiobook' logger (new code).
Readers poll with a per-page sequence cursor, so any number of browser tabs
can follow the log without draining it out from under each other.
"""

import logging
import threading
from collections import deque


class GuiLogBuffer:
    """Lock-protected ring buffer of (seq, line) with a monotonic sequence."""

    def __init__(self, maxlen=500):
        self._entries = deque(maxlen=maxlen)
        self._seq = 0
        self._lock = threading.Lock()

    def append(self, line):
        line = line.strip()
        if not line:
            return
        with self._lock:
            self._seq += 1
            self._entries.append((self._seq, line))

    def since(self, seq):
        """Return (lines, new_seq) for all entries newer than seq."""
        with self._lock:
            lines = [line for s, line in self._entries if s > seq]
            return lines, self._seq

    def clear(self):
        with self._lock:
            self._entries.clear()


class GuiLogHandler(logging.Handler):
    """Feeds log records into a GuiLogBuffer."""

    def __init__(self, buffer):
        super().__init__()
        self._buffer = buffer

    def emit(self, record):
        try:
            self._buffer.append(self.format(record))
        except Exception:
            self.handleError(record)


def setup_gui_logging(buffer):
    """Attach a GuiLogHandler to the named 'audiobook' logger. Idempotent."""
    logger = logging.getLogger('audiobook')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(isinstance(h, GuiLogHandler) for h in logger.handlers):
        handler = GuiLogHandler(buffer)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    return logger

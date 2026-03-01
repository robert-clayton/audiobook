"""Thread-aware stdout/stderr redirect that captures pipeline output for the GUI log."""

import io
import re
import sys
import threading
from collections import deque

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


class LogCapture(io.TextIOBase):
    """Replaces sys.stdout/sys.stderr to capture output from a specific thread.

    Output from the captured thread is stored in a ring buffer for the GUI.
    Output from all other threads passes through to the original stream.
    """

    def __init__(self, original, maxlen=500, shared_lines=None, shared_lock=None,
                 shared_history=None):
        self._original = original
        self._lines = shared_lines if shared_lines is not None else deque(maxlen=maxlen)
        self._history = shared_history if shared_history is not None else deque(maxlen=maxlen)
        self._capture_thread_id = None
        self._lock = shared_lock if shared_lock is not None else threading.Lock()

    @property
    def encoding(self):
        return getattr(self._original, 'encoding', 'utf-8')

    def set_capture_thread(self, thread_id):
        self._capture_thread_id = thread_id

    def write(self, s):
        if not s:
            return 0
        if threading.current_thread().ident == self._capture_thread_id:
            cleaned = ANSI_RE.sub('', s)
            # Split on newlines and carriage returns
            for line in cleaned.replace('\r', '\n').split('\n'):
                line = line.strip()
                if line:
                    with self._lock:
                        self._lines.append(line)
                        self._history.append(line)
            return len(s)
        # Pass through to original for other threads
        return self._original.write(s)

    def flush(self):
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return False

    def get_lines(self):
        """Return new lines since last call, draining the buffer."""
        with self._lock:
            lines = list(self._lines)
            self._lines.clear()
        return lines

    def get_history(self):
        """Return all lines in the history buffer (non-draining)."""
        with self._lock:
            return list(self._history)

    def clear(self):
        with self._lock:
            self._lines.clear()


def install():
    """Install LogCapture on stdout and stderr. Returns the stdout capture instance.

    Both stdout and stderr share the same line buffer and lock so all
    output appears in a single unified log.
    """
    stdout_capture = LogCapture(sys.stdout)
    stderr_capture = LogCapture(
        sys.stderr,
        shared_lines=stdout_capture._lines,
        shared_lock=stdout_capture._lock,
        shared_history=stdout_capture._history,
    )
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    # Wrap set_capture_thread so it updates both streams
    _original_set = stdout_capture.set_capture_thread

    def _set_both(thread_id):
        _original_set(thread_id)
        stderr_capture._capture_thread_id = thread_id

    stdout_capture.set_capture_thread = _set_both
    return stdout_capture


def uninstall(capture):
    """Restore original stdout/stderr."""
    if isinstance(sys.stdout, LogCapture):
        sys.stdout = sys.stdout._original
    if isinstance(sys.stderr, LogCapture):
        sys.stderr = sys.stderr._original

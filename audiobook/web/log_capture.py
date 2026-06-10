"""Thread-aware stdout/stderr redirect that captures pipeline output for the GUI."""

import io
import re
import sys
import threading

from .gui_log import GuiLogBuffer

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


class LogCapture(io.TextIOBase):
    """Replaces sys.stdout/sys.stderr to capture output from a specific thread.

    Output from the captured thread is forwarded (ANSI-stripped) into a shared
    GuiLogBuffer. Output from all other threads passes through to the original
    stream.
    """

    def __init__(self, original, buffer):
        self._original = original
        self._buffer = buffer
        self._capture_thread_id = None

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
                self._buffer.append(line)
            return len(s)
        # Pass through to original for other threads
        return self._original.write(s)

    def flush(self):
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return False


def install():
    """Install LogCapture on stdout and stderr.

    Returns (stdout_capture, buffer): the capture instance (for
    set_capture_thread) and the shared GuiLogBuffer the GUI reads from.
    """
    buffer = GuiLogBuffer()
    stdout_capture = LogCapture(sys.stdout, buffer)
    stderr_capture = LogCapture(sys.stderr, buffer)
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    # Wrap set_capture_thread so it updates both streams
    _original_set = stdout_capture.set_capture_thread

    def _set_both(thread_id):
        _original_set(thread_id)
        stderr_capture._capture_thread_id = thread_id

    stdout_capture.set_capture_thread = _set_both
    return stdout_capture, buffer


def uninstall(capture):
    """Restore original stdout/stderr."""
    if isinstance(sys.stdout, LogCapture):
        sys.stdout = sys.stdout._original
    if isinstance(sys.stderr, LogCapture):
        sys.stderr = sys.stderr._original

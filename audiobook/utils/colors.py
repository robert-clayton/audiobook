"""ANSI terminal color constants and status-line printing utility."""

import re
import shutil

GREEN   = "\033[92m"    # ANSI escape code for green
YELLOW  = "\033[93m"    # ANSI escape code for yellow
PURPLE  = "\033[95m"    # ANSI escape code for purple
RED     = "\033[91m"    # ANSI escape code for red
RESET   = "\033[0m"     # Reset color

def print_status(msg):
    """Print a single-line status message that overwrites the current terminal line.

    Args:
        msg: Status string (may contain ANSI color codes).
    """
    terminal_width = shutil.get_terminal_size(fallback=(80, 20)).columns
    visible_len = len(re.sub(r'\033\[[0-9;]*m', '', msg))
    padding = max(0, terminal_width - visible_len)
    print(f"\r{msg}{' ' * padding}", end='', flush=True)
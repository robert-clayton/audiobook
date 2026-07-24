"""Small server-side helpers shared across routers."""

import re


def natural_key(text):
    """Sort key ordering embedded numbers numerically (Chapter 2 < Chapter 10).

    Duplicated from web/shared.py — importing that module would pull in
    nicegui via web/theme.py, and this server package must stay nicegui-free.
    """
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', text or '')]

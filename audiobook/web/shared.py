"""Shared helpers for dashboard and series page UI."""

from .runner import PipelineState
from .theme import ACCENT, SUCCESS, ERROR, INFO, TEXT_DIM, BG, BORDER

STATE_COLORS = {
    PipelineState.IDLE: 'grey',
    PipelineState.SCRAPING: INFO,
    PipelineState.GENERATING: ACCENT,
    PipelineState.FINISHED: SUCCESS,
    PipelineState.ERROR: ERROR,
}


def status_html(label, color):
    """Render a status badge with a colored dot and label."""
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 6px;'
        f' font-size: 12px; color: {TEXT_DIM};">'
        f'<span style="display: inline-block; width: 8px; height: 8px;'
        f' border-radius: 50%; background: {color};"></span>'
        f'{label}</span>'
    )


def update_table_if_changed(table, new_rows):
    """Only assign table.rows if the data actually changed.

    Skipping the assignment preserves client-side sort order,
    pagination position, and scroll state in Quasar tables.
    """
    if table.rows != new_rows:
        table.rows = new_rows
        table.update()


def render_diff(diff_lines):
    """Render unified diff lines as color-coded HTML."""
    import html as html_mod

    parts = [f'<pre style="font-size: 13px; line-height: 1.5; margin: 0;'
             f' background: {BG}; padding: 8px; border-radius: 2px;'
             f' border: 1px solid {BORDER};">']
    for line in diff_lines:
        escaped = html_mod.escape(line)
        if line.startswith('+++') or line.startswith('---'):
            parts.append(f'<span style="color: {TEXT_DIM};">{escaped}</span>\n')
        elif line.startswith('@@'):
            parts.append(
                f'<span style="color: {INFO}; display: block;'
                f' margin-top: 4px;">{escaped}</span>\n')
        elif line.startswith('+'):
            parts.append(
                f'<span style="background: rgba(61,220,132,0.1); color: {SUCCESS};'
                f' display: inline-block; width: 100%;">{escaped}</span>\n')
        elif line.startswith('-'):
            parts.append(
                f'<span style="background: rgba(255,68,68,0.1); color: {ERROR};'
                f' display: inline-block; width: 100%;">{escaped}</span>\n')
        else:
            parts.append(f'{escaped}\n')
    parts.append('</pre>')
    return ''.join(parts)

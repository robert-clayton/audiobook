"""Job queue panel: current job with progress, queued jobs, and history."""

import time

from nicegui import ui

from .theme import ACCENT, SUCCESS, ERROR, INFO, TEXT_DIM, BG, BORDER

JOB_STATUS_COLORS = {
    'queued': INFO,
    'running': ACCENT,
    'done': SUCCESS,
    'failed': ERROR,
    'cancelled': TEXT_DIM,
}


def _fmt_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    return f'{seconds // 60}m {seconds % 60}s'


def create_queue_panel(runner):
    """Build the queue panel inside the current container.

    Returns a refresh function for the page's existing ui.timer.
    """
    container = ui.column().classes('w-full gap-1')
    _last_key = [None]

    def _dot(color):
        return (
            f'<span style="display: inline-block; width: 8px; height: 8px;'
            f' border-radius: 50%; background: {color}; flex-shrink: 0;"></span>'
        )

    def _render_current(cur):
        progress = cur.get('progress', {})
        with ui.row().classes('w-full items-center gap-2 no-wrap').style(
                f'background: {BG}; border: 1px solid {ACCENT}; border-radius: 2px;'
                f' padding: 8px 12px;'):
            ui.html(_dot(ACCENT))
            with ui.column().classes('gap-0 flex-grow min-w-0'):
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.label(cur['label']).classes('text-sm font-medium truncate')
                    if progress.get('series_total', 0) > 1:
                        ui.label(
                            f"[{progress.get('series_idx', '?')}/{progress['series_total']}]"
                        ).classes('text-xs').style(f'color: {TEXT_DIM}')
                    if cur.get('started_at'):
                        ui.label(_fmt_duration(time.time() - cur['started_at'])).classes(
                            'text-xs ml-auto').style(f'color: {TEXT_DIM}')
                detail_parts = []
                if progress.get('chapter'):
                    detail_parts.append(progress['chapter'])
                if detail_parts:
                    ui.label(' · '.join(detail_parts)).classes('text-xs truncate').style(
                        f'color: {TEXT_DIM}')
                if 'pct' in progress:
                    ui.linear_progress(
                        value=progress['pct'] / 100, show_value=False
                    ).classes('w-full').props('size=3px color=amber')
            ui.button(icon='close', on_click=lambda: _cancel(cur['id'])).props(
                'flat round dense size=sm').style(f'color: {ERROR}').tooltip(
                'Cancel (takes effect after current batch)')

    def _cancel(job_id):
        if runner.cancel(job_id):
            ui.notify('Cancelling — takes effect after the current batch', type='warning')

    def _cancel_queued(job_id):
        if runner.cancel(job_id):
            ui.notify('Removed from queue')

    def _render_queued(queued):
        for job in queued:
            with ui.row().classes('w-full items-center gap-2 no-wrap').style(
                    f'background: {BG}; border: 1px solid {BORDER}; border-radius: 2px;'
                    f' padding: 4px 12px;'):
                ui.html(_dot(INFO))
                ui.label(job['label']).classes('text-xs truncate flex-grow').style(
                    f'color: {TEXT_DIM}')
                ui.button(icon='close',
                          on_click=lambda _, jid=job['id']: _cancel_queued(jid)).props(
                    'flat round dense size=xs').style(f'color: {TEXT_DIM}').tooltip(
                    'Remove from queue')

    def _render_history(history):
        with ui.expansion(f'History ({len(history)})').classes('w-full').props(
                'dense header-class="text-caption"'):
            for job in history:
                color = JOB_STATUS_COLORS.get(job['status'], TEXT_DIM)
                with ui.row().classes('w-full items-center gap-2 no-wrap q-py-xs'):
                    ui.html(_dot(color))
                    label = ui.label(job['label']).classes('text-xs truncate').style(
                        f'color: {TEXT_DIM}')
                    if job['status'] == 'failed' and job.get('error'):
                        with label:
                            ui.tooltip(job['error'])
                    ui.label(job['status']).classes('text-xs').style(f'color: {color}')
                    if job.get('started_at') and job.get('finished_at'):
                        ui.label(
                            _fmt_duration(job['finished_at'] - job['started_at'])
                        ).classes('text-xs ml-auto').style(f'color: {TEXT_DIM}')

    def refresh():
        snap = runner.queue_snapshot()
        # Skip the rebuild when idle and nothing changed; always rebuild while
        # a job runs so elapsed time and progress advance.
        key = repr(snap)
        if snap['current'] is None and key == _last_key[0]:
            return
        _last_key[0] = key

        container.clear()
        if not snap['current'] and not snap['queued'] and not snap['history']:
            return
        with container:
            if snap['current']:
                _render_current(snap['current'])
            if snap['queued']:
                _render_queued(snap['queued'])
            if snap['history']:
                _render_history(snap['history'])

    refresh()
    return refresh

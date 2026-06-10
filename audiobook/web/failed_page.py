"""Failed-chapter triage page: all failures across series, with retry actions."""

from nicegui import ui, run

from .runner import PipelineRunner, PipelineState
from .theme import apply_theme, ACCENT, ERROR, TEXT_DIM
from .shared import STATE_COLORS, status_html, update_table_if_changed
from .queue_panel import create_queue_panel


def _build_failed_rows(runner, series_filter):
    """Query DB for failed chapters. Runs on threadpool."""
    try:
        db = runner.get_db()
    except Exception:
        return []
    try:
        failed = db.get_failed(series_filter)
    finally:
        db.close()

    return [{
        'id': ch['id'],
        'series': ch['series_name'],
        'title': ch['title'],
        'error': ch.get('error') or '',
        'retries': ch.get('retry_count') or 0,
        'updated_at': ch.get('updated_at') or '',
    } for ch in failed]


def create_failed_page(runner: PipelineRunner, series_filter=None):
    """Build the failed-chapters page UI. Called inside a @ui.page handler."""

    apply_theme()

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center gap-3'):
            ui.button(icon='arrow_back',
                on_click=lambda: ui.navigate.to('/')).props('flat round').style(
                f'color: {TEXT_DIM}')
            title = 'Failed Chapters'
            if series_filter:
                title += f' — {series_filter}'
            ui.label(title).classes('text-xl font-bold').style(f'color: {ERROR}')
            status_badge = ui.html(status_html('idle', 'grey')).classes('ml-auto')

        # Queue panel
        queue_refresh = create_queue_panel(runner)

        # Controls
        with ui.row().classes('w-full items-center gap-3'):
            search = ui.input(placeholder='filter...').props(
                'dense outlined clearable').classes('w-64')
            btn_retry_selected = ui.button(
                'Retry Selected', on_click=lambda: _retry_selected())
            btn_retry_selected.props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')

        failed_table = ui.table(
            columns=[
                {'name': 'series', 'label': 'Series', 'field': 'series', 'align': 'left', 'sortable': True},
                {'name': 'title', 'label': 'Chapter', 'field': 'title', 'align': 'left', 'sortable': True},
                {'name': 'error', 'label': 'Error', 'field': 'error', 'align': 'left',
                 'classes': 'max-w-xs truncate', 'sortable': True},
                {'name': 'retries', 'label': 'Retries', 'field': 'retries', 'align': 'center', 'sortable': True},
                {'name': 'updated_at', 'label': 'When', 'field': 'updated_at', 'align': 'center', 'sortable': True},
                {'name': 'actions', 'label': '', 'field': 'actions', 'align': 'center'},
            ],
            rows=[],
            row_key='id',
            selection='multiple',
            pagination={'rowsPerPage': 20, 'sortBy': 'updated_at', 'descending': True},
        ).classes('w-full').props('loading')
        search.bind_value_to(failed_table, 'filter')

        # Error cell with full text in tooltip
        failed_table.add_slot('body-cell-error', f'''
            <q-td :props="props" style="max-width: 320px; overflow: hidden;
                  text-overflow: ellipsis; white-space: nowrap;">
                {{{{ props.row.error }}}}
                <q-tooltip v-if="props.row.error" max-width="400px">
                    {{{{ props.row.error }}}}
                </q-tooltip>
            </q-td>
        ''')

        failed_table.add_slot('body-cell-actions', f'''
            <q-td :props="props">
                <q-btn @click.stop="$parent.$emit('retry', props.row)"
                       flat dense round icon="replay" size="sm"
                       style="color: {TEXT_DIM}">
                    <q-tooltip>Retry (regenerate)</q-tooltip>
                </q-btn>
            </q-td>
        ''')

        def _retry(row):
            job, created = runner.start_regenerate_chapter(
                row['series'], row['id'], chapter_title=row['title'])
            if created:
                ui.notify(f'Queued: {job.label()}')
            else:
                ui.notify(f'Already queued: {job.label()}', type='info')

        def _retry_selected():
            selected = failed_table.selected
            if not selected:
                ui.notify('No chapters selected', type='warning')
                return
            queued = 0
            for row in selected:
                _, created = runner.start_regenerate_chapter(
                    row['series'], row['id'], chapter_title=row['title'])
                if created:
                    queued += 1
            failed_table.selected = []
            ui.notify(f'Queued {queued} retr{"ies" if queued != 1 else "y"}')

        failed_table.on('retry', lambda e: _retry(e.args))

        empty_label = ui.label('No failed chapters.').classes('text-sm').style(
            f'color: {TEXT_DIM}')
        empty_label.set_visibility(False)

    _first_load = True

    async def refresh():
        nonlocal _first_load

        state = runner.state
        status_badge.set_content(status_html(state.value, STATE_COLORS.get(state, 'grey')))
        queue_refresh()

        rows = await run.io_bound(_build_failed_rows, runner, series_filter)
        update_table_if_changed(failed_table, rows)
        empty_label.set_visibility(not rows)
        if _first_load:
            failed_table.props(remove='loading')
            _first_load = False

    ui.timer(2.0, refresh)

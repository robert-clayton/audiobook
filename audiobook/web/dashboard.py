"""Main dashboard page UI for the NiceGUI web app."""

import urllib.parse
from nicegui import ui, run
from .runner import PipelineRunner, PipelineState
from .theme import apply_theme, ACCENT, SUCCESS, ERROR, INFO, TEXT_DIM, SURFACE, BG
from .shared import STATE_COLORS, status_html, update_table_if_changed
from .queue_panel import create_queue_panel
from .config_dialogs import open_add_series, open_narrator_settings
from .health import create_health_strip


def _build_dashboard_data(runner):
    """Query DB for series summary rows and stats. Runs on threadpool."""
    config = runner.get_config()
    enabled = [s for s in config.get('series', []) if s.get('enabled', True)]

    try:
        db = runner.get_db()
    except Exception:
        return {'rows': [], 'stats': None}

    try:
        rows = []
        for series in enabled:
            name = series.get('name', 'Unnamed')
            s = db.summary(name)
            series_info = db.get_series(name)
            rows.append({
                'name': name,
                'done': s['done'],
                'pending': s['pending'],
                'failed': s['failed'],
                'narrator': series_info.get('narrator', '') if series_info else series.get('narrator', ''),
            })
        return {'rows': rows, 'stats': db.stats()}
    finally:
        db.close()


def create_dashboard(runner: PipelineRunner):
    """Build the dashboard UI. Called inside a @ui.page handler."""

    apply_theme()

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center gap-3'):
            ui.label('Audiobook Pipeline').classes('text-xl font-bold').style(f'color: {ACCENT}')
            ui.link('failed', '/failed').classes('text-xs').style(
                f'color: {TEXT_DIM}; text-decoration: none; letter-spacing: 0.06em;')
            ui.link('speakers', '/speakers').classes('text-xs').style(
                f'color: {TEXT_DIM}; text-decoration: none; letter-spacing: 0.06em;')
            status_badge = ui.html(
                status_html('idle', 'grey')
            ).classes('ml-auto')
            if runner.dev_mode:
                ui.html(
                    f'<span style="border: 1px solid {ACCENT}; color: {ACCENT};'
                    f' font-size: 11px; padding: 1px 8px; border-radius: 2px;'
                    f' letter-spacing: 0.06em;">DEV</span>'
                )

        # Health + stats row
        with ui.row().classes('w-full items-center justify-between'):
            create_health_strip(runner)
            stats_label = ui.html('')

        # Controls row
        with ui.row().classes('w-full items-center gap-3'):
            btn_full = ui.button('Run Full Pipeline',
                on_click=lambda: _enqueue(runner.start_full))
            btn_full.props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
            btn_scrape = ui.button('Scrape Only',
                on_click=lambda: _enqueue(runner.start_scrape_only))
            btn_scrape.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')
            btn_sync = ui.button('Sync Filesystem',
                on_click=lambda: _sync_filesystem(runner, log_area))
            btn_sync.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')
            ui.button('Add Series', on_click=lambda: open_add_series(
                runner, on_saved=lambda name: ui.navigate.to(
                    f'/series/{urllib.parse.quote(name, safe="")}'))).props(
                'flat outline').style(
                f'color: {SUCCESS}; border-color: {SUCCESS}')
            ui.button('Narrators', on_click=lambda: open_narrator_settings(
                runner)).props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')

        # Job queue panel
        queue_refresh = create_queue_panel(runner)

        # Series table
        series_table = ui.table(
            columns=[
                {'name': 'name', 'label': 'Series', 'field': 'name', 'align': 'left', 'sortable': True},
                {'name': 'done', 'label': 'Done', 'field': 'done', 'align': 'center', 'sortable': True},
                {'name': 'pending', 'label': 'Pending', 'field': 'pending', 'align': 'center', 'sortable': True},
                {'name': 'failed', 'label': 'Failed', 'field': 'failed', 'align': 'center', 'sortable': True},
                {'name': 'narrator', 'label': 'Narrator', 'field': 'narrator', 'align': 'left'},
            ],
            rows=[],
            row_key='name',
            pagination={'rowsPerPage': 10, 'sortBy': 'name', 'descending': False},
        ).classes('w-full cursor-pointer').props('loading')

        # Clickable series name with accent hover
        series_table.add_slot('body-cell-name', f'''
            <q-td :props="props">
                <a :href="'/series/' + encodeURIComponent(props.row.name)"
                   @click.prevent="$parent.$emit('go_series', props.row)"
                   style="color: {ACCENT}; text-decoration: none; font-weight: 500;"
                   onmouseover="this.style.textDecoration='underline'"
                   onmouseout="this.style.textDecoration='none'">
                    {{{{ props.row.name }}}}
                </a>
            </q-td>
        ''')

        # Colored count cells
        series_table.add_slot('body-cell-done', f'''
            <q-td :props="props">
                <span :style="{{color: props.row.done ? '{SUCCESS}' : '{TEXT_DIM}'}}">
                    {{{{ props.row.done }}}}
                </span>
            </q-td>
        ''')
        series_table.add_slot('body-cell-pending', f'''
            <q-td :props="props">
                <span :style="{{color: props.row.pending ? '{INFO}' : '{TEXT_DIM}'}}">
                    {{{{ props.row.pending }}}}
                </span>
            </q-td>
        ''')
        series_table.add_slot('body-cell-failed', f'''
            <q-td :props="props">
                <a v-if="props.row.failed"
                   :href="'/failed?series=' + encodeURIComponent(props.row.name)"
                   @click.stop
                   style="color: {ERROR}; text-decoration: underline;">
                    {{{{ props.row.failed }}}}
                </a>
                <span v-else style="color: {TEXT_DIM}">{{{{ props.row.failed }}}}</span>
            </q-td>
        ''')

        series_table.on('go_series', lambda e: ui.navigate.to(
            f'/series/{urllib.parse.quote(e.args["name"], safe="")}'))
        series_table.on('row-click', lambda e: ui.navigate.to(
            f'/series/{urllib.parse.quote(e.args[1]["name"], safe="")}'))

        # Log panel
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('// LIVE LOG').style(
                f'font-size: 11px; color: {TEXT_DIM}; letter-spacing: 0.1em;'
                f' text-transform: uppercase;')
            ui.button('Clear', on_click=lambda: _clear_log(runner, log_area)).props(
                'flat dense').style(f'color: {TEXT_DIM}')

        log_area = ui.log(max_lines=200).classes('w-full h-64')
        lines, _log_seq = runner.get_log_since(0)
        for line in lines:
            log_area.push(line)

    _first_load = True

    async def refresh():
        nonlocal _first_load, _log_seq

        state = runner.state
        color = STATE_COLORS.get(state, 'grey')
        label = state.value
        if state == PipelineState.ERROR and runner.error_msg:
            label = f'error: {runner.error_msg[:60]}'
        status_badge.set_content(status_html(label, color))

        btn_sync.set_enabled(not runner.is_busy)
        queue_refresh()

        lines, _log_seq = runner.get_log_since(_log_seq)
        for line in lines:
            log_area.push(line)

        data = await run.io_bound(_build_dashboard_data, runner)
        update_table_if_changed(series_table, data['rows'])
        stats = data['stats']
        if stats:
            stats_label.set_content(
                f'<span style="font-size: 11px; color: {TEXT_DIM};">'
                f'{stats["done_count"]} chapters'
                f'<span style="margin: 0 8px; opacity: 0.3;">|</span>'
                f'{stats["tracked_hours"]:.1f} h tracked audio'
                f'<span style="margin: 0 8px; opacity: 0.3;">|</span>'
                f'{stats["done_7d"]} last 7d, {stats["done_30d"]} last 30d</span>'
            )
        if _first_load:
            series_table.props(remove='loading')
            _first_load = False

    ui.timer(2.0, refresh)


def _enqueue(start_fn):
    job, created = start_fn()
    if created:
        ui.notify(f'Queued: {job.label()}')
    else:
        ui.notify(f'Already queued: {job.label()}', type='info')


def _clear_log(runner, log_area):
    runner.clear_log()
    log_area.clear()


async def _sync_filesystem(runner, log_area):
    if runner.is_busy:
        ui.notify('Pipeline is busy', type='warning')
        return
    ui.notify('Syncing filesystem...')

    def do_sync():
        runner.sync_all()

    try:
        await run.io_bound(do_sync)
        log_area.push('[sync] Filesystem sync complete')
        ui.notify('Sync complete', type='positive')
    except Exception as ex:
        ui.notify(f'Error: {ex}', type='negative')

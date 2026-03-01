"""Main dashboard page UI for the NiceGUI web app."""

import urllib.parse
from nicegui import ui
from .runner import PipelineRunner, PipelineState
from .theme import apply_theme, ACCENT, SUCCESS, ERROR, INFO, TEXT_DIM, SURFACE, BG


_STATE_COLORS = {
    PipelineState.IDLE: 'grey',
    PipelineState.SCRAPING: INFO,
    PipelineState.GENERATING: ACCENT,
    PipelineState.FINISHED: SUCCESS,
    PipelineState.ERROR: ERROR,
}


def create_dashboard(runner: PipelineRunner):
    """Build the dashboard UI. Called inside a @ui.page handler."""

    apply_theme()

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center gap-3'):
            ui.label('Audiobook Pipeline').classes('text-xl font-bold').style(f'color: {ACCENT}')
            status_badge = ui.html(
                _status_html('idle', 'grey')
            ).classes('ml-auto')
            if runner.dev_mode:
                ui.html(
                    f'<span style="border: 1px solid {ACCENT}; color: {ACCENT};'
                    f' font-size: 11px; padding: 1px 8px; border-radius: 2px;'
                    f' letter-spacing: 0.06em;">DEV</span>'
                )

        # Controls row
        with ui.row().classes('w-full items-center gap-3'):
            btn_full = ui.button('Run Full Pipeline',
                on_click=lambda: _start_full(runner, btn_full, btn_scrape))
            btn_full.props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
            btn_scrape = ui.button('Scrape Only',
                on_click=lambda: _start_scrape(runner, btn_full, btn_scrape))
            btn_scrape.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')

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
            pagination={'rowsPerPage': 0, 'sortBy': 'name', 'descending': False},
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
                <span :style="{{color: props.row.failed ? '{ERROR}' : '{TEXT_DIM}'}}">
                    {{{{ props.row.failed }}}}
                </span>
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
        for line in runner.get_log_history():
            log_area.push(line)

    # Timer to poll runner state
    def refresh():
        state = runner.state
        color = _STATE_COLORS.get(state, 'grey')
        label = state.value
        if state == PipelineState.ERROR and runner.error_msg:
            label = f'error: {runner.error_msg[:60]}'
        status_badge.set_content(_status_html(label, color))

        running = runner.is_running
        btn_full.set_enabled(not running)
        btn_scrape.set_enabled(not running)

        for line in runner.get_log_lines():
            log_area.push(line)

        _refresh_table(runner, series_table)

    ui.timer(1.0, refresh)


def _status_html(label, color):
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 6px;'
        f' font-size: 12px; color: {TEXT_DIM};">'
        f'<span style="display: inline-block; width: 8px; height: 8px;'
        f' border-radius: 50%; background: {color};"></span>'
        f'{label}</span>'
    )


def _start_full(runner, btn_full, btn_scrape):
    btn_full.set_enabled(False)
    btn_scrape.set_enabled(False)
    runner.start_full()


def _start_scrape(runner, btn_full, btn_scrape):
    btn_full.set_enabled(False)
    btn_scrape.set_enabled(False)
    runner.start_scrape_only()


def _clear_log(runner, log_area):
    runner.clear_log()
    log_area.clear()


def _refresh_table(runner, table):
    """Refresh the series table from the DB."""
    config = runner.get_config()
    enabled = [s for s in config.get('series', []) if s.get('enabled', True)]
    if not enabled:
        return

    try:
        db = runner.get_db()
    except Exception:
        return

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
        table.rows = rows
        table.props(remove='loading')
        table.update()
    finally:
        db.close()

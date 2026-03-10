"""Series detail page with chapter list and per-chapter/series actions."""

import difflib
import html as html_mod
import os
from nicegui import ui, run
from .runner import PipelineRunner, PipelineState
from .theme import (
    apply_theme, ACCENT, SUCCESS, ERROR, INFO, TEXT_DIM, SURFACE, BG, BORDER,
)
from .shared import STATE_COLORS, status_html, update_table_if_changed, render_diff


def _build_chapter_data(runner, series_name):
    """Query DB for chapter rows and series info. Runs on threadpool."""
    try:
        db = runner.get_db()
    except Exception:
        return None

    try:
        summary = db.summary(series_name)
        series_info = db.get_series(series_name)
        chapters = db.get_chapters(series_name)
    finally:
        db.close()

    rows = []
    for ch in chapters:
        rows.append({
            'id': ch['id'],
            'title': ch['title'],
            'status': ch['status'],
            'published_date': ch.get('published_date') or '',
            'error': ch.get('error') or '',
        })

    narrator = series_info.get('narrator') or 'N/A' if series_info else 'N/A'
    source = series_info.get('source') or 'N/A' if series_info else 'N/A'
    summary_text = (
        f'{summary["done"]} done, {summary["pending"]} pending, '
        f'{summary["failed"]} failed'
    )

    return {
        'rows': rows,
        'narrator': narrator,
        'source': source,
        'summary_text': summary_text,
    }


# ── Extracted top-level handlers ────────────────────────────────


async def _handle_rescrape_series(runner, series_name, log_area):
    """Rescrape all chapters in a series, showing diff dialog."""
    if runner.is_running:
        ui.notify('Pipeline is busy', type='warning')
        return

    db = runner.get_db()
    try:
        chapter_count = len(db.get_chapters(series_name))
    finally:
        db.close()

    if not chapter_count:
        ui.notify('No chapters to check', type='info')
        return

    log_area.push(f'Rescrape series: checking {chapter_count} chapters...')
    ui.notify(f'Checking {chapter_count} chapters...')

    def do_fetch():
        from ..pipeline import fetch_rescrape_series
        db2 = runner.get_db()
        try:
            return fetch_rescrape_series(runner.get_config(), db2, series_name)
        finally:
            db2.close()

    try:
        changes, unavailable = await run.io_bound(do_fetch)
    except Exception as ex:
        ui.notify(f'Error: {ex}', type='negative')
        return

    if not changes and not unavailable:
        log_area.push('No changes detected')
        ui.notify('No changes detected', type='info')
        return

    if changes:
        log_area.push(f'{len(changes)} chapter(s) with changes')
        for c in changes:
            log_area.push(f'  {c["title"]} - {c["source_url"]}')
    if unavailable:
        log_area.push(
            f'{len(unavailable)} chapter(s) deleted/drafted')
        for u in unavailable:
            log_area.push(f'  {u["title"]} - {u["source_url"]}')

    # Pre-compute diffs
    chapter_diffs = []
    for change in changes:
        old_lines = change['old_text'].splitlines(keepends=False)
        new_lines = change['new_text'].splitlines(keepends=False)
        diff = list(difflib.unified_diff(
            old_lines, new_lines, lineterm=''))
        added = sum(1 for l in diff
                    if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff
                      if l.startswith('-') and not l.startswith('---'))
        chapter_diffs.append({'diff': diff, 'added': added, 'removed': removed})

    selected = {c['chapter_id']: True for c in changes}

    # Build summary text
    parts = []
    if changes:
        parts.append(f'{len(changes)} changed')
    if unavailable:
        parts.append(f'{len(unavailable)} deleted/drafted')
    summary = ', '.join(parts)

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-5xl').style(
            f'height: 85vh; background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label(f'Rescrape: {series_name}').classes('text-lg font-bold')
            with ui.row().classes('items-center gap-2'):
                ui.label(summary).classes('text-sm').style(
                    f'color: {TEXT_DIM}')
                ui.button(icon='close', on_click=dlg.close).props(
                    'flat round dense').style(f'color: {TEXT_DIM}')
        ui.separator()
        with ui.scroll_area().classes('w-full flex-grow'):
            # Unavailable chapters
            for u in unavailable:
                with ui.row().classes(
                        'w-full items-center q-py-xs q-px-sm'):
                    ui.icon('warning').style(f'color: {ACCENT}').classes('q-mr-sm')
                    ui.label(u['title']).classes('text-sm')
                    ui.html(
                        f'<span style="border: 1px solid {ACCENT}; color: {ACCENT};'
                        f' font-size: 11px; padding: 1px 8px; border-radius: 2px;'
                        f' margin-left: auto;">deleted / drafted</span>'
                    )
            # Changed chapters
            for change, d in zip(changes, chapter_diffs):
                ch_id = change['chapter_id']
                with ui.row().classes('w-full items-center no-wrap'):
                    ui.checkbox('', value=True).on_value_change(
                        lambda e, cid=ch_id: selected.__setitem__(
                            cid, e.value))
                    with ui.expansion(
                        f'{change["title"]}  '
                        f'(+{d["added"]} / -{d["removed"]})'
                    ).classes('w-full'):
                        ui.html(render_diff(d['diff']))
        ui.separator()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            async def apply_selected():
                to_apply = [c for c in changes
                            if selected.get(c['chapter_id'])]
                if not to_apply:
                    ui.notify('No chapters selected', type='warning')
                    return

                def do_apply():
                    from ..pipeline import apply_rescrape
                    db3 = runner.get_db()
                    try:
                        for c in to_apply:
                            apply_rescrape(
                                runner.get_config(), db3,
                                series_name, c['chapter_id'],
                                c['new_text'])
                    finally:
                        db3.close()

                await run.io_bound(do_apply)
                dlg.close()
                log_area.push(f'Applied {len(to_apply)} rescrape(s)')
                ui.notify(f'Updated {len(to_apply)} chapter(s)')

            if changes:
                ui.button('Apply Selected', on_click=apply_selected).props(
                    'flat outline').style(
                    f'color: {ACCENT}; border-color: {ACCENT}')
    dlg.open()


async def _handle_fix_filenames(runner, series_name, log_area):
    """Scan for filename mismatches and offer to rename."""
    def do_scan():
        from ..pipeline import scan_filename_fixes
        db = runner.get_db()
        try:
            return scan_filename_fixes(runner.get_config(), db, series_name)
        finally:
            db.close()

    try:
        fixes = await run.io_bound(do_scan)
    except Exception as ex:
        ui.notify(f'Error: {ex}', type='negative')
        return

    if not fixes:
        ui.notify('No filenames to fix', type='info')
        return

    log_area.push(f'Found {len(fixes)} filename(s) to fix')

    selected = {f['chapter_id']: True for f in fixes}

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-5xl').style(
            f'height: 85vh; background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label(f'Fix Filenames: {series_name}').classes('text-lg font-bold')
            with ui.row().classes('items-center gap-2'):
                ui.label(f'{len(fixes)} file(s) to rename').classes(
                    'text-sm').style(f'color: {TEXT_DIM}')
                ui.button(icon='close', on_click=dlg.close).props(
                    'flat round dense').style(f'color: {TEXT_DIM}')
        ui.separator()
        with ui.scroll_area().classes('w-full flex-grow'):
            for fix in fixes:
                ch_id = fix['chapter_id']
                with ui.row().classes('w-full items-center no-wrap q-py-xs'):
                    ui.checkbox('', value=True).on_value_change(
                        lambda e, cid=ch_id: selected.__setitem__(cid, e.value))
                    ui.html(
                        f'<span style="font-size: 13px;">'
                        f'<span style="color: {ERROR}; text-decoration: line-through;">'
                        f'{html_mod.escape(fix["old_title"])}</span>'
                        f'<span style="color: {TEXT_DIM}; margin: 0 8px;">&rarr;</span>'
                        f'<span style="color: {SUCCESS};">'
                        f'{html_mod.escape(fix["new_title"])}</span>'
                        f'</span>'
                    )
        ui.separator()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            async def apply_fixes():
                to_apply = [f for f in fixes if selected.get(f['chapter_id'])]
                if not to_apply:
                    ui.notify('No files selected', type='warning')
                    return

                dlg.close()

                def do_apply():
                    from ..pipeline import apply_filename_fixes
                    db2 = runner.get_db()
                    try:
                        return apply_filename_fixes(db2, to_apply)
                    finally:
                        db2.close()

                count = await run.io_bound(do_apply)
                log_area.push(f'Renamed {count} file(s)')
                ui.notify(f'Renamed {count} file(s)')

            ui.button('Apply', on_click=apply_fixes).props(
                'flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
    dlg.open()


async def _handle_resync(runner, series_name):
    """Resync filesystem state for a single series."""
    ui.notify(f'Resyncing {series_name}...')

    def do_resync():
        from ..pipeline import _find_series_config, detect_source_name
        db = runner.get_db()
        try:
            config = runner.get_config()
            series_cfg = _find_series_config(config, series_name)
            if series_cfg:
                url = series_cfg.get('url', '')
                db.upsert_series(
                    series_name, url=url,
                    source=detect_source_name(url),
                    narrator=series_cfg.get('narrator'),
                    latest_url=series_cfg.get('latest'),
                )
            out = config['config']['output_dir']
            raws_dir = os.path.join(out, series_name, 'raws')
            series_out = os.path.join(out, series_name)
            db.sync_filesystem(series_name, raws_dir, series_out)
        finally:
            db.close()

    try:
        await run.io_bound(do_resync)
        ui.notify('Resync complete', type='positive')
    except Exception as ex:
        ui.notify(f'Error: {ex}', type='negative')


# ── Page builder ────────────────────────────────────────────────


def create_series_page(runner: PipelineRunner, series_name: str):
    """Build the series detail page UI."""

    apply_theme()

    # Verify series exists — auto-register from config if not yet in DB
    db = runner.get_db()
    try:
        series = db.get_series(series_name)
        if not series:
            from ..pipeline import _find_series_config, detect_source_name
            series_cfg = _find_series_config(runner.get_config(), series_name)
            if series_cfg:
                url = series_cfg.get('url', '')
                db.upsert_series(
                    series_name, url=url,
                    source=detect_source_name(url),
                    narrator=series_cfg.get('narrator'),
                    latest_url=series_cfg.get('latest'),
                )
                out = runner.get_config()['config']['output_dir']
                raws_dir = os.path.join(out, series_name, 'raws')
                series_out = os.path.join(out, series_name)
                db.sync_filesystem(series_name, raws_dir, series_out)
                series = db.get_series(series_name)
    finally:
        db.close()

    if not series:
        with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
            ui.label(f'Series "{series_name}" not found').classes(
                'text-xl').style(f'color: {ERROR}')
            ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/')).props(
                'flat outline').style(f'color: {ACCENT}; border-color: {ACCENT}')
        return

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center gap-3'):
            ui.button(icon='arrow_back',
                on_click=lambda: ui.navigate.to('/')).props('flat round').style(
                f'color: {TEXT_DIM}').on('mouseover',
                lambda: None).classes('hover-accent')
            ui.label(series_name).classes('text-xl font-bold').style(
                f'color: {ACCENT}')
            status_badge = ui.html(
                status_html('idle', 'grey')
            ).classes('ml-auto')
            if runner.dev_mode:
                ui.html(
                    f'<span style="border: 1px solid {ACCENT}; color: {ACCENT};'
                    f' font-size: 11px; padding: 1px 8px; border-radius: 2px;'
                    f' letter-spacing: 0.06em;">DEV</span>'
                )

        # Compact info bar
        with ui.row().classes('w-full items-center gap-2'):
            narrator_label = ui.html(_info_bar_html(
                series.get('narrator') or 'N/A',
                series.get('source') or 'N/A', '...'))

        # Action buttons
        with ui.row().classes('w-full items-center gap-3'):
            btn_scrape = ui.button('Scrape',
                on_click=lambda: _series_action(runner,
                    lambda: runner.start_scrape_series(series_name),
                    f'Scraping {series_name}'))
            btn_scrape.props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
            btn_generate = ui.button('Generate',
                on_click=lambda: _series_action(runner,
                    lambda: runner.start_generate_series(series_name),
                    f'Generating {series_name}'))
            btn_generate.props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
            btn_rescrape_series = ui.button('Rescrape Series',
                on_click=lambda: _handle_rescrape_series(runner, series_name, log_area))
            btn_rescrape_series.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')
            btn_fix_filenames = ui.button('Fix Filenames',
                on_click=lambda: _handle_fix_filenames(runner, series_name, log_area))
            btn_fix_filenames.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')
            btn_resync = ui.button('Resync Filesystem',
                on_click=lambda: _handle_resync(runner, series_name))
            btn_resync.props('flat outline').style(
                f'color: {TEXT_DIM}; border-color: {TEXT_DIM}')

        # Chapter table
        chapter_table = ui.table(
            columns=[
                {'name': 'title', 'label': 'Title', 'field': 'title', 'align': 'left', 'sortable': True},
                {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'center', 'sortable': True},
                {'name': 'published_date', 'label': 'Published', 'field': 'published_date', 'align': 'center', 'sortable': True},
                {'name': 'actions', 'label': 'Actions', 'field': 'actions', 'align': 'center'},
            ],
            rows=[],
            row_key='id',
            pagination={'rowsPerPage': 20, 'sortBy': 'published_date', 'descending': False},
        ).classes('w-full').props('loading')

        # Status column with colored dots
        chapter_table.add_slot('body-cell-status', f'''
            <q-td :props="props">
                <span :style="{{
                    display: 'inline-block', width: '8px', height: '8px',
                    borderRadius: '50%', marginRight: '6px',
                    backgroundColor: {{'done':'{SUCCESS}', 'pending':'{INFO}', 'failed':'{ERROR}', 'processing':'{ACCENT}'}}[props.row.status] || '{TEXT_DIM}'
                }}"></span>
                <span style="font-size: 12px;">{{{{ props.row.status }}}}</span>
                <q-tooltip v-if="props.row.error">{{{{ props.row.error }}}}</q-tooltip>
            </q-td>
        ''')

        # Icon-only action buttons
        chapter_table.add_slot('body-cell-actions', f'''
            <q-td :props="props">
                <q-btn @click.stop="$parent.$emit('open_chapter', props.row)"
                       flat dense round icon="menu_book" size="sm"
                       style="color: {TEXT_DIM}">
                    <q-tooltip>Open Chapter</q-tooltip>
                </q-btn>
                <q-btn @click.stop="$parent.$emit('rescrape', props.row)"
                       flat dense round icon="refresh" size="sm" class="q-ml-xs"
                       style="color: {TEXT_DIM}">
                    <q-tooltip>Rescrape</q-tooltip>
                </q-btn>
                <q-btn @click.stop="$parent.$emit('regenerate', props.row)"
                       flat dense round icon="replay" size="sm" class="q-ml-xs"
                       style="color: {TEXT_DIM}">
                    <q-tooltip>Regenerate</q-tooltip>
                </q-btn>
            </q-td>
        ''')

        def handle_open_chapter(e):
            row = e.args
            db = runner.get_db()
            try:
                chapter = db.get_chapter_by_id(row['id'])
            finally:
                db.close()
            if not chapter or not chapter.get('raw_path'):
                ui.notify('No text file available', type='warning')
                return
            path = chapter['raw_path']
            if not os.path.exists(path):
                ui.notify('Text file not found on disk', type='warning')
                return
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            with ui.dialog() as dlg, ui.card().classes('w-full max-w-4xl').style(
                    f'height: 85vh; background: {SURFACE} !important;'):
                with ui.row().classes('w-full items-center justify-between q-mb-sm'):
                    ui.label(row['title']).classes('text-lg font-bold')
                    ui.button(icon='close', on_click=dlg.close).props(
                        'flat round dense').style(f'color: {TEXT_DIM}')
                if row['status'] == 'done':
                    ui.audio(f'/api/audio/{row["id"]}').classes('w-full')
                ui.separator()
                with ui.scroll_area().classes('w-full flex-grow'):
                    ui.html(
                        f'<pre style="white-space: pre-wrap; word-wrap: break-word;'
                        f' font-size: 13px; line-height: 1.6; color: {TEXT_DIM};'
                        f' background: {BG}; padding: 12px; border-radius: 2px;'
                        f' border: 1px solid {BORDER};">'
                        f'{html_mod.escape(content)}</pre>'
                    )
            dlg.open()

        def handle_regenerate(e):
            row = e.args
            if runner.is_running:
                ui.notify('Pipeline is busy', type='warning')
                return
            runner.start_regenerate_chapter(series_name, row['id'])
            ui.notify(f'Regenerating: {row["title"]}')

        async def handle_rescrape(e):
            row = e.args
            if runner.is_running:
                ui.notify('Pipeline is busy', type='warning')
                return
            ui.notify(f'Fetching: {row["title"]}...')

            def do_fetch():
                from ..pipeline import fetch_rescrape
                db = runner.get_db()
                try:
                    return fetch_rescrape(runner.get_config(), db, series_name, row['id'])
                finally:
                    db.close()

            try:
                old_text, new_text, source_url = await run.io_bound(do_fetch)
            except Exception as ex:
                ui.notify(f'Error: {ex}', type='negative')
                return

            log_area.push(f'Rescrape: {row["title"]}')
            log_area.push(f'Source: {source_url}')

            old_lines = old_text.splitlines(keepends=False)
            new_lines = new_text.splitlines(keepends=False)
            diff = list(difflib.unified_diff(
                old_lines, new_lines, fromfile='Current', tofile='New', lineterm=''))

            if not diff:
                ui.notify('No changes detected', type='info')
                return

            added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
            removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))

            with ui.dialog() as dlg, ui.card().classes('w-full max-w-5xl').style(
                    f'height: 85vh; background: {SURFACE} !important;'):
                with ui.row().classes('w-full items-center justify-between q-mb-sm'):
                    ui.label(f'Rescrape: {row["title"]}').classes('text-lg font-bold')
                    with ui.row().classes('items-center gap-2'):
                        ui.html(
                            f'<span style="color: {SUCCESS};">+{added}</span>'
                            f' / <span style="color: {ERROR};">-{removed}</span>'
                            f' lines'
                        )
                        ui.button(icon='close', on_click=dlg.close).props(
                            'flat round dense').style(f'color: {TEXT_DIM}')
                ui.separator()
                with ui.scroll_area().classes('w-full flex-grow'):
                    ui.html(render_diff(diff))
                ui.separator()
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Keep Old', on_click=dlg.close).props('flat').style(
                        f'color: {TEXT_DIM}')

                    async def accept():
                        def do_apply():
                            from ..pipeline import apply_rescrape
                            db2 = runner.get_db()
                            try:
                                apply_rescrape(
                                    runner.get_config(), db2,
                                    series_name, row['id'], new_text)
                            finally:
                                db2.close()

                        await run.io_bound(do_apply)
                        dlg.close()
                        ui.notify(f'Updated: {row["title"]}')

                    ui.button('Accept New', on_click=accept).props(
                        'flat outline').style(
                        f'color: {ACCENT}; border-color: {ACCENT}')
            dlg.open()

        chapter_table.on('open_chapter', handle_open_chapter)
        chapter_table.on('rescrape', handle_rescrape)
        chapter_table.on('regenerate', handle_regenerate)

        # Log panel
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('// LIVE LOG').style(
                f'font-size: 11px; color: {TEXT_DIM}; letter-spacing: 0.1em;'
                f' text-transform: uppercase;')
            ui.button('Clear', on_click=lambda: (runner.clear_log(), log_area.clear())).props(
                'flat dense').style(f'color: {TEXT_DIM}')

        log_area = ui.log(max_lines=200).classes('w-full h-64')
        for line in runner.get_log_history():
            log_area.push(line)

    _first_load = True
    _last_info_html = None

    async def refresh():
        nonlocal _first_load, _last_info_html

        # Update status badge
        state = runner.state
        color = STATE_COLORS.get(state, 'grey')
        label = state.value
        if state == PipelineState.ERROR and runner.error_msg:
            label = f'error: {runner.error_msg[:60]}'
        status_badge.set_content(status_html(label, color))

        # Enable/disable buttons
        running = runner.is_running
        btn_scrape.set_enabled(not running)
        btn_generate.set_enabled(not running)
        btn_rescrape_series.set_enabled(not running)
        btn_fix_filenames.set_enabled(not running)
        btn_resync.set_enabled(not running)

        # Update log
        for line in runner.get_log_lines():
            log_area.push(line)

        # Update DB data on threadpool
        data = await run.io_bound(_build_chapter_data, runner, series_name)
        if data is None:
            return

        # Update info bar only if changed
        new_info = _info_bar_html(data['narrator'], data['source'], data['summary_text'])
        if new_info != _last_info_html:
            narrator_label.set_content(new_info)
            _last_info_html = new_info

        update_table_if_changed(chapter_table, data['rows'])
        if _first_load:
            chapter_table.props(remove='loading')
            _first_load = False

    ui.timer(2.0, refresh)


def _info_bar_html(narrator, source, summary):
    return (
        f'<span style="font-size: 12px; color: {TEXT_DIM};">'
        f'<span style="opacity: 0.6;">narrator:</span> {narrator}'
        f'<span style="margin: 0 10px; opacity: 0.3;">|</span>'
        f'<span style="opacity: 0.6;">source:</span> {source}'
        f'<span style="margin: 0 10px; opacity: 0.3;">|</span>'
        f'{summary}</span>'
    )


def _series_action(runner, fn, msg):
    """Start a series-level action if pipeline is idle."""
    if runner.is_running:
        ui.notify('Pipeline is busy', type='warning')
        return
    fn()
    ui.notify(msg)

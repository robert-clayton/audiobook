"""Config editing dialogs: series editor, add-series, and narrator settings.

All writes go through runner.update_config (lock shared with the job worker),
so edits are safe while jobs run.
"""

from nicegui import ui

from ..pipeline import SCRAPER_MAP, is_local_source, detect_source_from_url
from ..speakers import list_speakers
from .theme import ACCENT, ERROR, SUCCESS, TEXT_DIM, SURFACE

SYSTEM_TYPES = ['bold', 'italic', 'bracket', 'angle', 'blockquote', 'table', 'center']


def _kv_editor(title, data, value_options=None):
    """Render an editable key→value list. Returns a getter for the current dict.

    value_options: when given, values use a dropdown (e.g. speaker names).
    """
    rows = [{'k': k, 'v': v} for k, v in (data or {}).items()]
    container = ui.column().classes('w-full gap-1')

    def render():
        container.clear()
        with container:
            for row in rows:
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.input(value=row['k'],
                             on_change=lambda e, r=row: r.update(k=e.value)).props(
                        'dense outlined').classes('flex-grow').props('placeholder=name')
                    if value_options:
                        ui.select(value_options, value=row['v'] if row['v'] in value_options else None,
                                  on_change=lambda e, r=row: r.update(v=e.value)).props(
                            'dense outlined').classes('flex-grow')
                    else:
                        ui.input(value=str(row['v']),
                                 on_change=lambda e, r=row: r.update(v=e.value)).props(
                            'dense outlined').classes('flex-grow').props('placeholder=value')
                    ui.button(icon='close', on_click=lambda _, r=row: (
                        rows.remove(r), render())).props('flat round dense size=xs').style(
                        f'color: {TEXT_DIM}')

    with ui.row().classes('w-full items-center justify-between'):
        ui.label(title).classes('text-xs uppercase').style(
            f'color: {TEXT_DIM}; letter-spacing: 0.08em;')
        ui.button(icon='add', on_click=lambda: (
            rows.append({'k': '', 'v': ''}), render())).props(
            'flat round dense size=xs').style(f'color: {ACCENT}')
    render()

    def get():
        return {r['k'].strip(): r['v'] for r in rows
                if r['k'] and str(r['k']).strip() and r['v'] not in (None, '')}
    return get


def open_series_editor(runner, series_name, on_saved=None):
    """Dialog to edit one series' config fields."""
    config = runner.get_config()
    series_cfg = None
    for s in config.get('series', []):
        if s.get('name') == series_name:
            series_cfg = s
            break
    if not series_cfg:
        ui.notify(f"Series '{series_name}' not found in config", type='negative')
        return

    speakers = list_speakers()
    system = series_cfg.get('system', {}) or {}
    had_system = 'system' in series_cfg

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-3xl').style(
            f'max-height: 85vh; background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label(f'Edit Config: {series_name}').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dlg.close).props(
                'flat round dense').style(f'color: {TEXT_DIM}')
        ui.separator()

        with ui.scroll_area().classes('w-full').style('height: 60vh;'):
            with ui.column().classes('w-full gap-3 q-pr-md'):
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    narrator_sel = ui.select(
                        speakers, value=series_cfg.get('narrator'),
                        label='Narrator').props('dense outlined').classes('flex-grow')
                    enabled_sw = ui.switch(
                        'Enabled', value=series_cfg.get('enabled', True))

                # Scrape cursor — guarded
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    latest_input = ui.input(
                        label='latest (scrape cursor)',
                        value=series_cfg.get('latest', '')).props(
                        'dense outlined readonly').classes('flex-grow')
                    unlock_sw = ui.switch('unlock').props('dense')

                    def toggle_lock(e):
                        if e.value:
                            latest_input.props(remove='readonly')
                            ui.notify('Careful — the scraper resumes from this URL',
                                      type='warning')
                        else:
                            latest_input.props('readonly')
                    unlock_sw.on_value_change(toggle_lock)

                ui.separator()
                get_replacements = _kv_editor(
                    'Replacements (word → pronunciation)',
                    series_cfg.get('replacements', {}))

                ui.separator()
                get_mappings = _kv_editor(
                    'Mappings (character → speaker)',
                    series_cfg.get('mappings', {}), value_options=speakers)

                ui.separator()
                ui.label('System voice').classes('text-xs uppercase').style(
                    f'color: {TEXT_DIM}; letter-spacing: 0.08em;')
                with ui.row().classes('w-full items-center gap-3 no-wrap'):
                    sys_voice = ui.select(
                        speakers, value=system.get('voice'),
                        label='Voice').props('dense outlined clearable').classes('w-48')
                    sys_modulate = ui.switch('Modulate', value=system.get('modulate', True))
                    sys_speed = ui.number(
                        label='Speed', value=system.get('speed', 1.0),
                        min=0.5, max=2.0, step=0.05).props('dense outlined').classes('w-28')
                sys_types = ui.select(
                    SYSTEM_TYPES, value=system.get('type', []), multiple=True,
                    label='Element types').props('dense outlined use-chips').classes('w-full')

        ui.separator()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            def save():
                new_latest = latest_input.value.strip()
                types = sys_types.value or []

                def mutate(cfg):
                    target = None
                    for s in cfg.get('series', []):
                        if s.get('name') == series_name:
                            target = s
                            break
                    if target is None:
                        raise ValueError(f"Series '{series_name}' missing from config")
                    target['narrator'] = narrator_sel.value
                    target['enabled'] = enabled_sw.value
                    if unlock_sw.value and new_latest:
                        target['latest'] = new_latest

                    replacements = get_replacements()
                    if replacements:
                        target['replacements'] = replacements
                    else:
                        target.pop('replacements', None)

                    mappings = get_mappings()
                    if mappings:
                        target['mappings'] = mappings
                    else:
                        target.pop('mappings', None)

                    # Only write a system section if it does something
                    if types or had_system:
                        new_system = dict(target.get('system', {}) or {})
                        new_system['type'] = types
                        if sys_voice.value:
                            new_system['voice'] = sys_voice.value
                        else:
                            new_system.pop('voice', None)
                        new_system['modulate'] = sys_modulate.value
                        new_system['speed'] = sys_speed.value or 1.0
                        target['system'] = new_system

                try:
                    runner.update_config(mutate)
                except Exception as ex:
                    ui.notify(f'Error saving config: {ex}', type='negative')
                    return
                dlg.close()
                ui.notify(f'Saved config for {series_name}', type='positive')
                if on_saved:
                    on_saved()

            ui.button('Save', on_click=save).props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
    dlg.open()


def open_add_series(runner, on_saved=None):
    """Dialog to add a new series to the config."""
    speakers = list_speakers()

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-2xl').style(
            f'background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label('Add Series').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dlg.close).props(
                'flat round dense').style(f'color: {TEXT_DIM}')
        ui.separator()

        name_input = ui.input(label='Series name').props('dense outlined').classes('w-full')
        url_input = ui.input(
            label="Series URL (or 'local' for manually managed chapters)").props(
            'dense outlined').classes('w-full')
        latest_input = ui.input(
            label='First chapter URL (scrape starting point)').props(
            'dense outlined').classes('w-full')
        narrator_sel = ui.select(speakers, label='Narrator').props(
            'dense outlined').classes('w-full')

        def on_url_change(e):
            latest_input.set_visibility(not is_local_source(e.value or ''))
        url_input.on_value_change(on_url_change)

        ui.separator()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            def save():
                name = (name_input.value or '').strip()
                url = (url_input.value or '').strip()
                latest = (latest_input.value or '').strip()
                local = is_local_source(url)

                if not name:
                    ui.notify('Series name is required', type='warning')
                    return
                if any(s.get('name') == name
                       for s in runner.get_config().get('series', [])):
                    ui.notify(f"Series '{name}' already exists", type='warning')
                    return
                if not local and not detect_source_from_url(url):
                    supported = ', '.join(SCRAPER_MAP)
                    ui.notify(f"URL must be 'local' or from: {supported}", type='warning')
                    return
                if not local and not latest:
                    ui.notify('First chapter URL is required for scraped series',
                              type='warning')
                    return
                if not narrator_sel.value:
                    ui.notify('Pick a narrator', type='warning')
                    return

                entry = {'name': name, 'url': 'local' if local else url,
                         'narrator': narrator_sel.value}
                if not local:
                    entry['latest'] = latest

                def mutate(cfg):
                    cfg.setdefault('series', []).append(entry)

                try:
                    runner.update_config(mutate)
                except Exception as ex:
                    ui.notify(f'Error saving config: {ex}', type='negative')
                    return
                dlg.close()
                ui.notify(f'Added series: {name}', type='positive')
                if on_saved:
                    on_saved(name)

            ui.button('Add', on_click=save).props('flat outline').style(
                f'color: {SUCCESS}; border-color: {SUCCESS}')
    dlg.open()


def open_narrator_settings(runner):
    """Dialog to edit per-narrator pause/volume settings."""
    config = runner.get_config()
    narrators = dict(config.get('config', {}).get('narrators', {}) or {})
    narrators.setdefault('default', {})
    speakers = list_speakers()

    # name -> {'pause': ..., 'volume': ...}
    rows = [{'name': n, 'pause': v.get('pause'), 'volume': v.get('volume')}
            for n, v in narrators.items()]
    rows.sort(key=lambda r: (r['name'] != 'default', r['name']))

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-2xl').style(
            f'max-height: 80vh; background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label('Narrator Settings').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dlg.close).props(
                'flat round dense').style(f'color: {TEXT_DIM}')
        ui.separator()

        container = ui.column().classes('w-full gap-1')

        def render():
            container.clear()
            with container:
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.label('narrator').classes('text-xs flex-grow').style(
                        f'color: {TEXT_DIM}')
                    ui.label('pause (s)').classes('text-xs w-28').style(
                        f'color: {TEXT_DIM}')
                    ui.label('volume').classes('text-xs w-28').style(
                        f'color: {TEXT_DIM}')
                    ui.label('').classes('w-8')
                for row in rows:
                    with ui.row().classes('w-full items-center gap-2 no-wrap'):
                        ui.label(row['name']).classes('text-sm flex-grow')
                        ui.number(value=row['pause'], min=0, max=5, step=0.05,
                                  on_change=lambda e, r=row: r.update(pause=e.value)).props(
                            'dense outlined').classes('w-28')
                        ui.number(value=row['volume'], min=0.1, max=3, step=0.05,
                                  on_change=lambda e, r=row: r.update(volume=e.value)).props(
                            'dense outlined').classes('w-28')
                        if row['name'] != 'default':
                            ui.button(icon='close', on_click=lambda _, r=row: (
                                rows.remove(r), render())).props(
                                'flat round dense size=xs').style(f'color: {TEXT_DIM}')
                        else:
                            ui.label('').classes('w-8')

        render()

        with ui.row().classes('w-full items-center gap-2'):
            existing = {r['name'] for r in rows}
            add_sel = ui.select([s for s in speakers if s not in existing],
                                label='Add narrator').props('dense outlined').classes('w-64')

            def add_narrator():
                if not add_sel.value:
                    return
                rows.append({'name': add_sel.value, 'pause': None, 'volume': None})
                add_sel.set_options([s for s in speakers
                                     if s not in {r['name'] for r in rows}])
                add_sel.set_value(None)
                render()

            ui.button(icon='add', on_click=add_narrator).props(
                'flat round dense').style(f'color: {ACCENT}')

        ui.separator()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            def save():
                def mutate(cfg):
                    out = {}
                    for r in rows:
                        entry = {}
                        if r['pause'] is not None:
                            entry['pause'] = r['pause']
                        if r['volume'] is not None:
                            entry['volume'] = r['volume']
                        if entry or r['name'] == 'default':
                            out[r['name']] = entry
                    cfg.setdefault('config', {})['narrators'] = out

                try:
                    runner.update_config(mutate)
                except Exception as ex:
                    ui.notify(f'Error saving config: {ex}', type='negative')
                    return
                dlg.close()
                ui.notify('Narrator settings saved', type='positive')

            ui.button('Save', on_click=save).props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
    dlg.open()

"""Speaker manager: list voice profiles, play reference audio, edit transcripts."""

import os
import wave

from nicegui import ui

from ..speakers import list_speakers, speaker_wav_path, transcript_path
from .runner import PipelineRunner
from .theme import apply_theme, ACCENT, ERROR, SUCCESS, TEXT_DIM, SURFACE, WARNING


def _wav_duration(path):
    try:
        with wave.open(path, 'r') as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return None


def _used_by(config, speaker):
    """Where a speaker is referenced in config: narrator, mapping, or system voice."""
    uses = []
    for series in config.get('series', []):
        name = series.get('name', '?')
        if series.get('narrator') == speaker:
            uses.append(f'{name} (narrator)')
        if speaker in (series.get('mappings', {}) or {}).values():
            uses.append(f'{name} (mapping)')
        if (series.get('system', {}) or {}).get('voice') == speaker:
            uses.append(f'{name} (system)')
    return uses


def _build_speaker_rows(config):
    rows = []
    for name in list_speakers():
        duration = _wav_duration(speaker_wav_path(name))
        has_transcript = os.path.isfile(transcript_path(name))
        rows.append({
            'name': name,
            'duration': f'{duration:.1f}s' if duration else '?',
            'transcript': has_transcript,
            'used_by': _used_by(config, name),
        })
    return rows


def create_speakers_page(runner: PipelineRunner):
    """Build the speakers page UI. Called inside a @ui.page handler."""

    apply_theme()

    with ui.column().classes('w-full max-w-5xl mx-auto p-4 gap-4'):
        with ui.row().classes('w-full items-center gap-3'):
            ui.button(icon='arrow_back',
                on_click=lambda: ui.navigate.to('/')).props('flat round').style(
                f'color: {TEXT_DIM}')
            ui.label('Speakers').classes('text-xl font-bold').style(f'color: {ACCENT}')
            ui.label('Reference voices for cloning — a missing transcript falls back'
                     ' to x-vector-only mode (lower quality)').classes(
                'text-xs ml-auto').style(f'color: {TEXT_DIM}')

        rows = _build_speaker_rows(runner.get_config())
        if not rows:
            ui.label('No speakers found in speakers/.').style(f'color: {TEXT_DIM}')
            return

        for row in rows:
            with ui.row().classes('w-full items-center gap-3 no-wrap').style(
                    f'background: {SURFACE}; border-radius: 2px; padding: 8px 16px;'):
                with ui.column().classes('gap-0 w-56 flex-shrink-0'):
                    ui.label(row['name']).classes('text-sm font-medium')
                    ui.label(row['duration']).classes('text-xs').style(
                        f'color: {TEXT_DIM}')
                if row['transcript']:
                    badge_color, badge_text = SUCCESS, 'transcript'
                else:
                    badge_color, badge_text = WARNING, 'no transcript'
                ui.html(
                    f'<span style="border: 1px solid {badge_color}; color: {badge_color};'
                    f' font-size: 11px; padding: 1px 8px; border-radius: 2px;'
                    f' white-space: nowrap;">{badge_text}</span>'
                )
                used = ', '.join(row['used_by']) if row['used_by'] else 'unused'
                ui.label(used).classes('text-xs truncate flex-grow').style(
                    f'color: {TEXT_DIM}')
                ui.audio(f'/api/speaker_audio/{row["name"]}').classes(
                    'w-64 flex-shrink-0')
                ui.button(icon='description',
                          on_click=lambda _, n=row['name']: _open_transcript(n)).props(
                    'flat round dense').style(f'color: {TEXT_DIM}').tooltip(
                    'View / edit transcript')


def _open_transcript(name):
    path = transcript_path(name)
    content = ''
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

    with ui.dialog() as dlg, ui.card().classes('w-full max-w-3xl').style(
            f'background: {SURFACE} !important;'):
        with ui.row().classes('w-full items-center justify-between q-mb-sm'):
            ui.label(f'Transcript: {name}').classes('text-lg font-bold')
            ui.button(icon='close', on_click=dlg.close).props(
                'flat round dense').style(f'color: {TEXT_DIM}')
        if not content:
            ui.label('No transcript yet — adding one significantly improves'
                     ' voice cloning quality.').classes('text-xs').style(
                f'color: {WARNING}')
        editor = ui.textarea(value=content).classes('w-full').props(
            'outlined autogrow input-style="font-size: 13px;"')
        ui.label('Note: an already-loaded TTS model keeps its cached voice prompt'
                 ' until the job queue drains and the model unloads.').classes(
            'text-xs').style(f'color: {TEXT_DIM}')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dlg.close).props('flat').style(
                f'color: {TEXT_DIM}')

            def save():
                text = (editor.value or '').strip()
                if not text:
                    ui.notify('Transcript is empty — not saved', type='warning')
                    return
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text + '\n')
                dlg.close()
                ui.notify(f'Transcript saved for {name}', type='positive')

            ui.button('Save', on_click=save).props('flat outline').style(
                f'color: {ACCENT}; border-color: {ACCENT}')
    dlg.open()

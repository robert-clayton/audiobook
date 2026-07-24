"""Speaker voice profiles: listing, transcript read/write."""

import os
import wave

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...speakers import list_speakers, speaker_wav_path, transcript_path
from ..deps import get_runner

router = APIRouter(prefix='/api/speakers', tags=['speakers'])


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


class TranscriptBody(BaseModel):
    text: str


@router.get('')
def get_speakers(runner=Depends(get_runner)):
    # Sync def → threadpool: reads WAV headers from disk.
    config = runner.get_config()
    rows = []
    for name in list_speakers():
        duration = _wav_duration(speaker_wav_path(name))
        rows.append({
            'name': name,
            'duration_s': duration,
            'has_transcript': os.path.isfile(transcript_path(name)),
            'used_by': _used_by(config, name),
        })
    return rows


@router.get('/{name}/transcript')
def get_transcript(name: str):
    if name not in list_speakers():
        raise HTTPException(status_code=404, detail='Speaker not found')
    path = transcript_path(name)
    text = ''
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    return {'text': text}


@router.put('/{name}/transcript')
def put_transcript(name: str, body: TranscriptBody):
    if name not in list_speakers():
        raise HTTPException(status_code=404, detail='Speaker not found')
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Transcript is empty — not saved')
    with open(transcript_path(name), 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    return {'ok': True}

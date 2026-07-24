"""Audio streaming endpoints (paths identical to the legacy NiceGUI app)."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ...speakers import list_speakers, speaker_wav_path
from ..deps import get_runner, open_db

router = APIRouter(prefix='/api', tags=['media'])


@router.get('/audio/{chapter_id}')
def serve_audio(chapter_id: int, runner=Depends(get_runner)):
    with open_db(runner) as db:
        chapter = db.get_chapter_by_id(chapter_id)
    if not chapter or not chapter.get('output_path'):
        raise HTTPException(status_code=404, detail='Audio not found')
    path = chapter['output_path']
    if not os.path.exists(path):
        alt = os.path.splitext(path)[0] + ('.mp3' if path.endswith('.wav') else '.wav')
        if os.path.exists(alt):
            path = alt
        else:
            raise HTTPException(status_code=404, detail='Audio file not found')
    media_type = 'audio/mpeg' if path.endswith('.mp3') else 'audio/wav'
    return FileResponse(path, media_type=media_type)


@router.get('/speaker_audio/{name}')
def serve_speaker_audio(name: str):
    # Validate against the actual speaker list — no path traversal
    if name not in list_speakers():
        raise HTTPException(status_code=404, detail='Speaker not found')
    return FileResponse(speaker_wav_path(name), media_type='audio/wav')

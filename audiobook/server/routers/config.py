"""Config read + narrator settings, and option lists for the editor dialogs."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...speakers import list_speakers
from ..deps import get_runner

router = APIRouter(prefix='/api/config', tags=['config'])

SYSTEM_TYPES = ['bold', 'italic', 'bracket', 'angle', 'blockquote', 'table', 'center']


@router.get('')
async def get_config(runner=Depends(get_runner)):
    # Localhost single-user tool — the raw config is fine to expose.
    return runner.get_config()


@router.get('/meta')
def get_meta():
    from ...pipeline import SCRAPER_MAP
    return {
        'speakers': list_speakers(),
        'system_types': SYSTEM_TYPES,
        'sources': list(SCRAPER_MAP),
    }


class TtsSettingsBody(BaseModel):
    tts_batch_size: Optional[int] = None
    tts_verbose: Optional[bool] = None


@router.put('/tts')
def put_tts_settings(body: TtsSettingsBody, runner=Depends(get_runner)):
    """Global TTS tuning knobs. Applied from the next job (per-job config reload)."""
    if body.tts_batch_size is not None and not 1 <= body.tts_batch_size <= 32:
        raise HTTPException(status_code=400,
                            detail='tts_batch_size must be between 1 and 32')

    def mutate(cfg):
        c = cfg.setdefault('config', {})
        if body.tts_batch_size is not None:
            c['tts_batch_size'] = body.tts_batch_size
        if body.tts_verbose is not None:
            c['tts_verbose'] = body.tts_verbose

    runner.update_config(mutate)
    return {'ok': True}


class NarratorEntry(BaseModel):
    pause: Optional[float] = None
    volume: Optional[float] = None


class NarratorsBody(BaseModel):
    narrators: dict[str, NarratorEntry]


@router.put('/narrators')
def put_narrators(body: NarratorsBody, runner=Depends(get_runner)):
    def mutate(cfg):
        out = {}
        for name, entry in body.narrators.items():
            data = {}
            if entry.pause is not None:
                data['pause'] = entry.pause
            if entry.volume is not None:
                data['volume'] = entry.volume
            if data or name == 'default':
                out[name] = data
        out.setdefault('default', {})
        cfg.setdefault('config', {})['narrators'] = out

    runner.update_config(mutate)
    return {'ok': True}

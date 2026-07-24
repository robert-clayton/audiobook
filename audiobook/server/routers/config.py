"""Config read + narrator settings, and option lists for the editor dialogs."""

from typing import Optional

from fastapi import APIRouter, Depends
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

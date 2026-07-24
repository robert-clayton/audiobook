"""Per-chapter endpoints: text read/edit, regenerate, rescrape, failed triage."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_runner, open_db, require_idle
from .jobs import submit_response

router = APIRouter(prefix='/api', tags=['chapters'])


@router.get('/failed')
def get_failed(series: Optional[str] = None, runner=Depends(get_runner)):
    with open_db(runner) as db:
        failed = db.get_failed(series)
    return [{
        'id': ch['id'],
        'series': ch['series_name'],
        'title': ch['title'],
        'error': ch.get('error') or '',
        'retries': ch.get('retry_count') or 0,
        'updated_at': ch.get('updated_at') or '',
    } for ch in failed]


@router.get('/chapters/{chapter_id}')
def get_chapter(chapter_id: int, runner=Depends(get_runner)):
    with open_db(runner) as db:
        chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail='Chapter not found')
    return chapter


@router.get('/chapters/{chapter_id}/text')
def get_chapter_text(chapter_id: int, series: str, runner=Depends(get_runner)):
    """Raw chapter text plus the cleaned-for-TTS preview."""
    with open_db(runner) as db:
        chapter = db.get_chapter_by_id(chapter_id)
    if not chapter or not chapter.get('raw_path'):
        raise HTTPException(status_code=404, detail='No text file available')
    path = chapter['raw_path']
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail='Text file not found on disk')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    from ...pipeline import _find_series_config
    from ...validators.validate_file import clean_text
    series_cfg = _find_series_config(runner.get_config(), series) or {}
    replacements = series_cfg.get('replacements', {})

    return {
        'title': chapter['title'],
        'status': chapter['status'],
        'text': content,
        'cleaned': clean_text(content, replacements),
    }


class TextEditBody(BaseModel):
    series: str
    text: str
    regenerate: bool = False


@router.put('/chapters/{chapter_id}/text')
def put_chapter_text(chapter_id: int, body: TextEditBody, runner=Depends(get_runner)):
    """Save an edited chapter text (resets the chapter to pending); optionally
    queue an immediate regenerate."""
    from ...pipeline import apply_text_edit
    with open_db(runner) as db:
        chapter = db.get_chapter_by_id(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail='Chapter not found')
        apply_text_edit(runner.get_config(), db, body.series, chapter_id, body.text)

    if body.regenerate:
        result = runner.start_regenerate_chapter(
            body.series, chapter_id, chapter_title=chapter['title'])
        return {'ok': True, **submit_response(result)}
    return {'ok': True}


class ChapterJobBody(BaseModel):
    series: str
    title: Optional[str] = None


@router.post('/chapters/{chapter_id}/regenerate')
async def regenerate_chapter(chapter_id: int, body: ChapterJobBody,
                             runner=Depends(get_runner)):
    return submit_response(runner.start_regenerate_chapter(
        body.series, chapter_id, chapter_title=body.title))


class BulkItem(BaseModel):
    id: int
    series: str
    title: Optional[str] = None


class BulkBody(BaseModel):
    chapters: list[BulkItem]


@router.post('/chapters/regenerate-bulk')
async def regenerate_bulk(body: BulkBody, runner=Depends(get_runner)):
    queued = 0
    for ch in body.chapters:
        _job, created = runner.start_regenerate_chapter(
            ch.series, ch.id, chapter_title=ch.title)
        if created:
            queued += 1
    return {'queued': queued, 'requested': len(body.chapters)}


class RescrapePreviewBody(BaseModel):
    series: str


@router.post('/chapters/{chapter_id}/rescrape-preview')
def rescrape_preview(chapter_id: int, body: RescrapePreviewBody,
                     runner=Depends(get_runner)):
    """Fetch fresh chapter text from source without writing anything."""
    require_idle(runner)
    from ...pipeline import fetch_rescrape
    with open_db(runner) as db:
        old_text, new_text, source_url = fetch_rescrape(
            runner.get_config(), db, body.series, chapter_id)
    return {'old_text': old_text, 'new_text': new_text, 'source_url': source_url}


class RescrapeApplyBody(BaseModel):
    series: str
    new_text: str


@router.post('/chapters/{chapter_id}/rescrape-apply')
def rescrape_apply(chapter_id: int, body: RescrapeApplyBody, runner=Depends(get_runner)):
    from ...pipeline import apply_rescrape
    with open_db(runner) as db:
        apply_rescrape(runner.get_config(), db, body.series, chapter_id, body.new_text)
    return {'ok': True}

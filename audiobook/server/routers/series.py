"""Series endpoints: dashboard summary, detail, chapters, actions, config edits.

All heavy handlers are sync `def` — FastAPI runs them on its threadpool,
keeping SMB-backed SQLite reads and config-lock writes off the event loop.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_runner, open_db, require_idle
from ..util import natural_key
from .jobs import submit_response

router = APIRouter(prefix='/api/series', tags=['series'])


# ── Read endpoints ──────────────────────────────────────────────


@router.get('')
def list_series(runner=Depends(get_runner)):
    """Dashboard data: per-series status counts + generation stats."""
    config = runner.get_config()
    enabled = [s for s in config.get('series', []) if s.get('enabled', True)]

    with open_db(runner) as db:
        rows = []
        for series in enabled:
            name = series.get('name', 'Unnamed')
            s = db.summary(name)
            series_info = db.get_series(name)
            rows.append({
                'name': name,
                'done': s['done'],
                'pending': s['pending'],
                'processing': s['processing'],
                'failed': s['failed'],
                'narrator': (series_info.get('narrator') if series_info else None)
                            or series.get('narrator', ''),
                'url': series.get('url', ''),
            })
        return {'series': rows, 'stats': db.stats()}


def _register_series_from_config(runner, db, series_name):
    """Auto-register a series that exists in config but not yet in the DB."""
    from ...pipeline import _find_series_config, detect_source_name
    series_cfg = _find_series_config(runner.get_config(), series_name)
    if not series_cfg:
        return None
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
    return db.get_series(series_name)


@router.get('/{name}')
def get_series(name: str, runner=Depends(get_runner)):
    from ...pipeline import _find_series_config
    with open_db(runner) as db:
        series = db.get_series(name)
        if not series:
            series = _register_series_from_config(runner, db, name)
        if not series:
            raise HTTPException(status_code=404, detail=f"Series '{name}' not found")
        summary = db.summary(name)
    return {
        'name': name,
        'narrator': series.get('narrator') or None,
        'source': series.get('source') or None,
        'summary': summary,
        'config': _find_series_config(runner.get_config(), name),
    }


@router.get('/{name}/chapters')
def get_chapters(name: str, runner=Depends(get_runner)):
    with open_db(runner) as db:
        chapters = db.get_chapters(name)

    rows = []
    for ch in chapters:
        rows.append({
            'id': ch['id'],
            'title': ch['title'],
            'status': ch['status'],
            'published_date': ch.get('published_date') or '',
            'error': ch.get('error') or '',
            'raw_path': ch.get('raw_path') or '',
            'pct': None,
        })

    # Natural order (Chapter 2 before Chapter 10) as the default order;
    # the DB returns rows sorted lexically by raw_path.
    rows.sort(key=lambda r: natural_key(r['title']))

    # Fold the live generation pct into the row currently being processed.
    cur = runner.queue_snapshot()['current']
    if cur:
        prog = cur.get('progress', {})
        if prog.get('raw_path') and prog.get('pct') is not None:
            for r in rows:
                if r['raw_path'] == prog['raw_path'] and r['status'] == 'processing':
                    r['pct'] = prog['pct']

    return rows


# ── Job submissions ─────────────────────────────────────────────


@router.post('/{name}/scrape')
async def scrape_series(name: str, runner=Depends(get_runner)):
    return submit_response(runner.start_scrape_series(name))


@router.post('/{name}/generate')
async def generate_series(name: str, runner=Depends(get_runner)):
    return submit_response(runner.start_generate_series(name))


# ── Config mutations ────────────────────────────────────────────


class AddSeriesBody(BaseModel):
    name: str
    url: str
    latest: Optional[str] = None
    narrator: str


@router.post('')
def add_series(body: AddSeriesBody, runner=Depends(get_runner)):
    from ...pipeline import SCRAPER_MAP, detect_source_from_url, is_local_source

    name = body.name.strip()
    url = body.url.strip()
    latest = (body.latest or '').strip()
    local = is_local_source(url)

    if not name:
        raise HTTPException(status_code=400, detail='Series name is required')
    if any(s.get('name') == name for s in runner.get_config().get('series', [])):
        raise HTTPException(status_code=400, detail=f"Series '{name}' already exists")
    if not local and not detect_source_from_url(url):
        supported = ', '.join(SCRAPER_MAP)
        raise HTTPException(status_code=400,
                            detail=f"URL must be 'local' or from: {supported}")
    if not local and not latest:
        raise HTTPException(status_code=400,
                            detail='First chapter URL is required for scraped series')
    if not body.narrator:
        raise HTTPException(status_code=400, detail='Pick a narrator')

    entry = {'name': name, 'url': 'local' if local else url, 'narrator': body.narrator}
    if not local:
        entry['latest'] = latest

    runner.update_config(lambda cfg: cfg.setdefault('series', []).append(entry))
    return {'ok': True, 'name': name}


class SystemConfig(BaseModel):
    voice: Optional[str] = None
    modulate: bool = True
    speed: float = 1.0
    type: list[str] = []


class SeriesConfigPatch(BaseModel):
    narrator: Optional[str] = None
    enabled: Optional[bool] = None
    latest: Optional[str] = None            # applied only when present (SPA "unlock")
    replacements: Optional[dict] = None     # empty dict removes the key
    mappings: Optional[dict] = None         # empty dict removes the key
    system: Optional[SystemConfig] = None


@router.patch('/{name}/config')
def patch_series_config(name: str, body: SeriesConfigPatch, runner=Depends(get_runner)):
    fields = body.model_dump(exclude_unset=True)

    def mutate(cfg):
        target = None
        for s in cfg.get('series', []):
            if s.get('name') == name:
                target = s
                break
        if target is None:
            raise ValueError(f"Series '{name}' missing from config")

        if 'narrator' in fields and fields['narrator']:
            target['narrator'] = fields['narrator']
        if 'enabled' in fields and fields['enabled'] is not None:
            target['enabled'] = fields['enabled']
        if fields.get('latest'):
            target['latest'] = fields['latest'].strip()

        for key in ('replacements', 'mappings'):
            if key in fields and fields[key] is not None:
                cleaned = {str(k).strip(): v for k, v in fields[key].items()
                           if str(k).strip() and v not in (None, '')}
                if cleaned:
                    target[key] = cleaned
                else:
                    target.pop(key, None)

        if 'system' in fields and fields['system'] is not None:
            sys_cfg = fields['system']
            # Only write a system section if it does something (parity with
            # the legacy editor: types set, or the series already had one).
            if sys_cfg['type'] or 'system' in target:
                new_system = dict(target.get('system', {}) or {})
                new_system['type'] = sys_cfg['type']
                if sys_cfg['voice']:
                    new_system['voice'] = sys_cfg['voice']
                else:
                    new_system.pop('voice', None)
                new_system['modulate'] = sys_cfg['modulate']
                new_system['speed'] = sys_cfg['speed'] or 1.0
                target['system'] = new_system

    try:
        runner.update_config(mutate)
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
    return {'ok': True}


# ── Interactive flows (bypass the queue; 409 while busy) ────────


@router.post('/{name}/resync')
def resync_series(name: str, runner=Depends(get_runner)):
    require_idle(runner)
    from ...pipeline import _find_series_config, detect_source_name
    config = runner.get_config()
    with open_db(runner) as db:
        series_cfg = _find_series_config(config, name)
        if series_cfg:
            url = series_cfg.get('url', '')
            db.upsert_series(
                name, url=url,
                source=detect_source_name(url),
                narrator=series_cfg.get('narrator'),
                latest_url=series_cfg.get('latest'),
            )
        out = config['config']['output_dir']
        raws_dir = os.path.join(out, name, 'raws')
        series_out = os.path.join(out, name)
        db.sync_filesystem(name, raws_dir, series_out)
    return {'ok': True}


@router.post('/{name}/rescrape-preview')
def rescrape_series_preview(name: str, runner=Depends(get_runner)):
    """Fetch fresh text for every chapter — long-running (network per chapter)."""
    require_idle(runner)
    from ...pipeline import fetch_rescrape_series
    with open_db(runner) as db:
        changes, unavailable = fetch_rescrape_series(runner.get_config(), db, name)
    return {'changes': changes, 'unavailable': unavailable}


class RescrapeApplyItem(BaseModel):
    chapter_id: int
    new_text: str


class RescrapeApplyBody(BaseModel):
    chapters: list[RescrapeApplyItem]


@router.post('/{name}/rescrape-apply')
def rescrape_series_apply(name: str, body: RescrapeApplyBody, runner=Depends(get_runner)):
    from ...pipeline import apply_rescrape
    with open_db(runner) as db:
        for item in body.chapters:
            apply_rescrape(runner.get_config(), db, name, item.chapter_id, item.new_text)
    return {'applied': len(body.chapters)}


@router.post('/{name}/filename-fixes/scan')
def scan_filename_fixes(name: str, runner=Depends(get_runner)):
    require_idle(runner)
    from ...pipeline import scan_filename_fixes as scan
    with open_db(runner) as db:
        fixes = scan(runner.get_config(), db, name)
    # Strip absolute file paths from the response — clients only need titles.
    return {'fixes': [{'chapter_id': f['chapter_id'],
                       'old_title': f['old_title'],
                       'new_title': f['new_title']} for f in fixes]}


class FilenameFixApplyBody(BaseModel):
    chapter_ids: list[int]


@router.post('/{name}/filename-fixes/apply')
def apply_filename_fixes(name: str, body: FilenameFixApplyBody, runner=Depends(get_runner)):
    require_idle(runner)
    # Re-run the scan server-side and filter by id — never trust paths
    # echoed back from the client.
    from ...pipeline import apply_filename_fixes as apply, scan_filename_fixes as scan
    wanted = set(body.chapter_ids)
    with open_db(runner) as db:
        fixes = [f for f in scan(runner.get_config(), db, name)
                 if f['chapter_id'] in wanted]
        count = apply(db, fixes)
    return {'renamed': count}

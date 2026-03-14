"""Reusable pipeline phases extracted from cli.py for use by both CLI and GUI."""

import glob
import os
import warnings
from .scrapers.royalroad import RoyalRoadScraper
from .scrapers.scribblehub import ScribbleHubScraper
from .processors.processing import process_series, process_chapter
from .utils.colors import GREEN, PURPLE, RED, YELLOW, RESET, print_status
from urllib.parse import urlparse
from requests.exceptions import HTTPError

SCRAPER_MAP = {
    "royalroad.com": RoyalRoadScraper,
    "scribblehub.com": ScribbleHubScraper,
}

SOURCE_NAME_MAP = {
    "royalroad.com": "royalroad",
    "scribblehub.com": "scribblehub",
}


def detect_source_from_url(url):
    """Determine which scraper to use based on the URL's domain."""
    domain = urlparse(url).netloc.lower()
    for key, scraper_cls in SCRAPER_MAP.items():
        if key in domain:
            return scraper_cls
    return None


def is_local_source(url):
    """Return True if the series uses locally-managed raws (url == 'local')."""
    return url.strip().lower() == 'local' if url else False


def detect_source_name(url):
    """Return a short source identifier (e.g. 'royalroad') for a URL, or None."""
    if is_local_source(url):
        return 'local'
    domain = urlparse(url).netloc.lower()
    for key, name in SOURCE_NAME_MAP.items():
        if key in domain:
            return name
    return None


def get_enabled_series(config):
    """Return list of enabled series from config."""
    return [s for s in config['series'] if s.get('enabled', True)]


def _find_series_config(config, series_name):
    """Find series config dict by name, or None."""
    for s in config.get('series', []):
        if s.get('name') == series_name:
            return s
    return None


def _build_series_cfg(config, series_cfg):
    """Merge global TTS config into series config."""
    tts_engine = config['config'].get('tts_engine', 'qwen')
    narrators_config = config['config'].get('narrators', {})
    return {**series_cfg, 'tts_engine': tts_engine, 'narrators': narrators_config}


def _delete_chapter_outputs(raw_path, output_base, series_name):
    """Delete all output/temp files for a chapter to prepare for regeneration."""
    base = os.path.splitext(os.path.basename(raw_path))[0]
    series_out = os.path.join(output_base, series_name)

    for ext in ('.mp3', '.wav'):
        p = os.path.join(series_out, f"{base}{ext}")
        if os.path.exists(p):
            os.remove(p)

    cleaned = raw_path.replace('.txt', '_cleaned.txt')
    if os.path.exists(cleaned):
        os.remove(cleaned)

    for f in glob.glob(os.path.join('tmp', f"{base}_part*")):
        os.remove(f)


# ── All-series phases (used by CLI and full pipeline) ────────


def run_scrape_phase(config, db):
    """Phase 1: Scrape new chapters for all enabled series.

    Returns True if any new chapters were found.
    """
    series_to_scrape = get_enabled_series(config)
    total = len(series_to_scrape)
    raws_subdir = "raws"

    if total == 0:
        print(f"{YELLOW}No enabled series found in the configuration.{RESET}")
        return False

    # Populate series table from config
    for series in series_to_scrape:
        url = series.get('url', '')
        db.upsert_series(
            series['name'],
            url=url,
            source=detect_source_name(url),
            narrator=series.get('narrator'),
            latest_url=series.get('latest'),
        )

    new_chapter_found = False
    for idx, series in enumerate(series_to_scrape):
        url = series.get('url', '')

        if is_local_source(url):
            continue

        scraper_cls = detect_source_from_url(url)

        if not scraper_cls:
            print(
                f"{YELLOW}Could not determine scraper for URL: {url}. "
                f"Skipping '{series.get('name', 'Unnamed')}'...{RESET}"
            )
            continue

        output_dir = os.path.join(config['config']['output_dir'], series.get('name'), raws_subdir)
        scraper = scraper_cls(series, output_dir, db=db)
        try:
            print_status(
                f"{GREEN}[{idx+1}/{total}] "
                f"Scraping {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
            )
            series['latest'], found = scraper.scrape_chapters()
            if found:
                new_chapter_found = True
        except HTTPError as e:
            if e.response.status_code == 429:
                print(
                    f"\n{YELLOW}Skipping series due to rate limiting (HTTP 429): {series['name']}{RESET}"
                )
                continue
            else:
                raise
        except Exception as e:
            print(f"\n{RED}An unexpected error occurred for '{series.get('name', 'Unnamed')}': {e}{RESET}")
            continue

    if not new_chapter_found:
        print_status(f"{GREEN}Scraping Complete - No New Chapters!{RESET}")
    print()
    return new_chapter_found


def run_audio_phase(config, db, dev_mode=False):
    """Phase 2: sync_filesystem + process_series for all enabled series."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        tmp = 'tmp'
        out = config['config']['output_dir']
        raws_subdir = "raws"

        os.makedirs(tmp, exist_ok=True)
        os.makedirs(out, exist_ok=True)

        tts_engine = config['config'].get('tts_engine', 'qwen')
        narrators_config = config['config'].get('narrators', {})
        series_to_process = get_enabled_series(config)
        total = len(series_to_process)

        for idx, series in enumerate(series_to_process):
            series_name = series.get('name', 'Unnamed')
            raws_dir = os.path.join(out, series_name, raws_subdir)
            series_out = os.path.join(out, series_name)
            db.sync_filesystem(series_name, raws_dir, series_out)

            series_cfg = {**series, 'tts_engine': tts_engine, 'narrators': narrators_config}
            print_status(
                f"{GREEN}[{idx+1}/{total}] "
                f"Generating {PURPLE}{series_name}{RESET}"
            )
            input_dir = os.path.join(config['config']['output_dir'], series_name, raws_subdir)
            process_series(input_dir, series_cfg, out, tmp, db=db, dev_mode=dev_mode)
    print()


def print_summary(config, db):
    """Print summary of chapter statuses for all enabled series."""
    series_to_process = get_enabled_series(config)
    print(f"{GREEN}--- Chapter Summary ---{RESET}")
    for series in series_to_process:
        name = series.get('name', 'Unnamed')
        s = db.summary(name)
        parts = []
        if s['done']:
            parts.append(f"{GREEN}{s['done']} done{RESET}")
        if s['pending']:
            parts.append(f"{YELLOW}{s['pending']} pending{RESET}")
        if s['failed']:
            parts.append(f"{RED}{s['failed']} failed{RESET}")
        if parts:
            print(f"  {PURPLE}{name}{RESET}: {', '.join(parts)}")


# ── Single-series operations (used by GUI) ───────────────────


def run_scrape_single_series(config, db, series_name):
    """Scrape chapters for a single series. Returns True if new chapters found."""
    series_cfg = _find_series_config(config, series_name)
    if not series_cfg:
        print(f"{RED}Series '{series_name}' not found in config{RESET}")
        return False

    url = series_cfg.get('url', '')
    db.upsert_series(
        series_name, url=url, source=detect_source_name(url),
        narrator=series_cfg.get('narrator'), latest_url=series_cfg.get('latest'),
    )

    if is_local_source(url):
        print(f"{YELLOW}Local series '{series_name}' — skipping scrape{RESET}")
        return False

    scraper_cls = detect_source_from_url(url)
    if not scraper_cls:
        print(f"{YELLOW}Could not determine scraper for URL: {url}{RESET}")
        return False

    output_dir = os.path.join(config['config']['output_dir'], series_name, "raws")
    scraper = scraper_cls(series_cfg, output_dir, db=db)

    try:
        print_status(f"{GREEN}Scraping {PURPLE}{series_name}{RESET}")
        series_cfg['latest'], found = scraper.scrape_chapters()
        if not found:
            print_status(f"{GREEN}No new chapters for {PURPLE}{series_name}{RESET}")
        print()
        return found
    except HTTPError as e:
        if e.response.status_code == 429:
            print(f"\n{YELLOW}Rate limited (HTTP 429): {series_name}{RESET}")
            return False
        raise
    except Exception as e:
        print(f"\n{RED}Error scraping '{series_name}': {e}{RESET}")
        return False


def run_audio_single_series(config, db, series_name, dev_mode=False):
    """Generate audio for a single series."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        out = config['config']['output_dir']

        os.makedirs('tmp', exist_ok=True)
        os.makedirs(out, exist_ok=True)

        series_cfg = _find_series_config(config, series_name)
        if not series_cfg:
            print(f"{RED}Series '{series_name}' not found in config{RESET}")
            return

        raws_dir = os.path.join(out, series_name, "raws")
        series_out = os.path.join(out, series_name)
        db.sync_filesystem(series_name, raws_dir, series_out)

        full_cfg = _build_series_cfg(config, series_cfg)
        print_status(f"{GREEN}Generating {PURPLE}{series_name}{RESET}")
        process_series(raws_dir, full_cfg, out, 'tmp', db=db, dev_mode=dev_mode)
    print()


# ── Single-chapter operations (used by GUI) ──────────────────


def regenerate_chapter(config, db, series_name, chapter_id, dev_mode=False):
    """Delete output for a chapter and re-run TTS."""
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        print(f"{RED}Chapter not found{RESET}")
        return

    series_cfg = _find_series_config(config, series_name)
    if not series_cfg:
        print(f"{RED}Series config not found for '{series_name}'{RESET}")
        return

    raw_path = chapter['raw_path']
    out = config['config']['output_dir']
    _delete_chapter_outputs(raw_path, out, series_name)
    db.reset_chapter(raw_path)

    full_cfg = _build_series_cfg(config, series_cfg)
    print(f"{GREEN}Regenerating: {PURPLE}{chapter['title']}{RESET}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        os.makedirs('tmp', exist_ok=True)
        process_chapter(raw_path, full_cfg, out, 'tmp', db=db, dev_mode=dev_mode)


def rescrape_chapter(config, db, series_name, chapter_id):
    """Re-fetch a chapter from source, overwrite raw text, and reset for processing."""
    old_text, new_text, _url = fetch_rescrape(config, db, series_name, chapter_id)
    chapter = db.get_chapter_by_id(chapter_id)
    apply_rescrape(config, db, series_name, chapter_id, new_text)
    print(f"{GREEN}Re-scraped: {PURPLE}{chapter['title']}{RESET}")


def fetch_rescrape(config, db, series_name, chapter_id):
    """Fetch fresh chapter content without writing. Returns (old_text, new_text, source_url)."""
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        raise ValueError("Chapter not found")

    series_cfg = _find_series_config(config, series_name)
    if not series_cfg:
        raise ValueError(f"Series config not found for '{series_name}'")

    url = series_cfg.get('url', '')
    if is_local_source(url):
        raise ValueError("Cannot rescrape a local series")
    scraper_cls = detect_source_from_url(url)
    if not scraper_cls:
        raise ValueError(f"Could not determine scraper for URL: {url}")

    raws_dir = os.path.dirname(chapter['raw_path'])
    scraper = scraper_cls(series_cfg, raws_dir, db=db)

    source_url = chapter.get('source_url')
    if not source_url:
        source_url = scraper.resolve_chapter_url(chapter['title'])
        if not source_url:
            raise ValueError("Could not find chapter URL in TOC")
        db.update_source_url(chapter['id'], source_url)

    _title, new_content, _pub_date = scraper.fetch_chapter_content(source_url)

    old_content = ''
    if os.path.exists(chapter['raw_path']):
        with open(chapter['raw_path'], 'r', encoding='utf-8') as f:
            old_content = f.read()

    return old_content, new_content, source_url


def apply_rescrape(config, db, series_name, chapter_id, new_content):
    """Write new content to the chapter file and reset for processing."""
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return

    with open(chapter['raw_path'], 'w', encoding='utf-8') as f:
        f.write(new_content)

    out = config['config']['output_dir']
    _delete_chapter_outputs(chapter['raw_path'], out, series_name)
    db.reset_chapter(chapter['raw_path'])


def fetch_rescrape_series(config, db, series_name):
    """Fetch all chapters for a series and return diffs for changed ones.

    Returns (changes, unavailable) where:
    - changes: list of {chapter_id, title, old_text, new_text, source_url}
    - unavailable: list of {chapter_id, title, source_url} for deleted/drafted chapters
    """
    from .scrapers.base import ChapterUnavailableError

    series_cfg = _find_series_config(config, series_name)
    if not series_cfg:
        raise ValueError(f"Series config not found for '{series_name}'")

    url = series_cfg.get('url', '')
    if is_local_source(url):
        raise ValueError("Cannot rescrape a local series")
    scraper_cls = detect_source_from_url(url)
    if not scraper_cls:
        raise ValueError(f"Could not determine scraper for URL: {url}")

    raws_dir = os.path.join(config['config']['output_dir'], series_name, 'raws')
    scraper = scraper_cls(series_cfg, raws_dir, db=db)
    chapters = db.get_chapters(series_name)

    # Resolve missing source_urls in bulk (one cached TOC fetch)
    for ch in chapters:
        if not ch.get('source_url'):
            resolved = scraper.resolve_chapter_url(ch['title'])
            if resolved:
                db.update_source_url(ch['id'], resolved)
                ch['source_url'] = resolved

    changes = []
    unavailable = []
    for ch in chapters:
        source_url = ch.get('source_url')
        if not source_url:
            continue
        try:
            _title, new_content, _pub_date = scraper.fetch_chapter_content(source_url)
        except ChapterUnavailableError:
            unavailable.append({
                'chapter_id': ch['id'],
                'title': ch['title'],
                'source_url': source_url,
            })
            continue
        except Exception:
            continue

        old_content = ''
        if os.path.exists(ch['raw_path']):
            with open(ch['raw_path'], 'r', encoding='utf-8') as f:
                old_content = f.read()

        if old_content != new_content:
            changes.append({
                'chapter_id': ch['id'],
                'title': ch['title'],
                'old_text': old_content,
                'new_text': new_content,
                'source_url': source_url,
            })

    return changes, unavailable


def scan_filename_fixes(config, db, series_name):
    """Scan for chapter files whose names contain the series title and propose renames.

    Returns list of dicts: {chapter_id, old_title, new_title, files: [(old_path, new_path), ...]}
    """
    import re

    series_cfg = _find_series_config(config, series_name)
    if not series_cfg:
        raise ValueError(f"Series config not found for '{series_name}'")

    out = config['config']['output_dir']
    series_dir = os.path.join(out, series_name)
    raws_dir = os.path.join(series_dir, 'raws')

    chapters = db.get_chapters(series_name)
    if not chapters:
        return []

    cfg_name = series_cfg.get('name', series_name)
    results = []

    for ch in chapters:
        raw_path = ch.get('raw_path', '')
        if not raw_path or not os.path.exists(raw_path):
            continue

        fname = os.path.basename(raw_path)
        base, ext = os.path.splitext(fname)
        if ext != '.txt' or base.endswith('_cleaned'):
            continue

        # Split date prefix from title: "2025-01-27_B1 Chapter 3 - Series Name"
        parts = base.split('_', 1)
        if len(parts) < 2:
            continue
        date_prefix, title_part = parts

        # Try to strip series name suffix from the title
        new_title = _strip_series_from_title(title_part, cfg_name)
        if new_title == title_part:
            continue

        # Build rename pairs for all related files
        old_base = f'{date_prefix}_{title_part}'
        new_base = f'{date_prefix}_{new_title}'
        file_renames = []

        # Raw .txt
        file_renames.append((raw_path, os.path.join(raws_dir, f'{new_base}.txt')))
        # Output .mp3 / .wav
        for ext_ in ('.mp3', '.wav'):
            old_out = os.path.join(series_dir, f'{old_base}{ext_}')
            if os.path.exists(old_out):
                file_renames.append((old_out, os.path.join(series_dir, f'{new_base}{ext_}')))

        results.append({
            'chapter_id': ch['id'],
            'old_title': title_part,
            'new_title': new_title,
            'files': file_renames,
        })

    return results


def apply_filename_fixes(db, fixes):
    """Rename files and update DB paths for a list of fixes from scan_filename_fixes.

    Commits after each chapter so ctrl+c leaves DB consistent with disk.
    """
    applied = 0
    for fix in fixes:
        # Skip if already applied (e.g. double-click)
        old_raw, new_raw = fix['files'][0]
        existing = db._conn.execute(
            "SELECT id FROM chapters WHERE raw_path=?", (old_raw,)
        ).fetchone()
        if not existing:
            continue

        for old_path, new_path in fix['files']:
            if os.path.exists(old_path) and not os.path.exists(new_path):
                os.rename(old_path, new_path)

        db._conn.execute(
            "UPDATE chapters SET raw_path=?, title=?, updated_at=? WHERE id=?",
            (new_raw, fix['new_title'], db._now(), fix['chapter_id']),
        )
        for old_path, new_path in fix['files'][1:]:
            db._conn.execute(
                "UPDATE chapters SET output_path=?, updated_at=? WHERE output_path=?",
                (new_path, db._now(), old_path),
            )
        db._conn.commit()
        applied += 1
        total = len(fixes)
        print(f"[rename] [{applied}/{total}] {fix['old_title']} → {fix['new_title']}")

    return applied


def _strip_series_from_title(title, series_name):
    """Strip a series name from a chapter title (suffix, prefix, and promo cruft).

    Delegates to the shared RoyalRoad stripping logic.
    """
    from .scrapers.royalroad import _strip_rr_cruft
    return _strip_rr_cruft(title, series_name)

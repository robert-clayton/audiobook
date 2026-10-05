"""Scraper for a local markdown translation repo (zirusmusings-content layout).

Treats a checked-out translation repo as a chapter source so a translated
series behaves like a scraped one: Scrape imports new chapters, Rescrape diffs
the markdown against the stored raw, and the per-chapter dialogs all work.

Series URL form:  file:///abs/path/to/series/ade
Chapter URL form: file:///abs/path/to/series/ade/21/500.md

Chapters live in {series}/{volume}/{chapter}.md with YAML frontmatter. Titles
are emitted as "Chapter N - {title}". The per-series `filename_style` config key
picks how files are named:

  dated   (default)  2022-03-13T1157.00001_Chapter 1 - Foo.txt
                     The `written` date (original posting datetime) prefixes the
                     name, so a plain filename sort is publication order.
                     Chapters without a date are skipped.
  chapter            Chapter 1 - Foo.txt
                     Order comes from the chapter number (DB chapter_index, the
                     dashboard's natural sort, and the MP3 track tag). `written`
                     is still stored and tagged into the MP3, but is optional.
"""

import os
import re
from urllib.parse import urlparse, quote, unquote

from .base import BaseScraper
from ..utils.colors import YELLOW, RESET

_FRONTMATTER_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n', re.S)
# Markdown image refs carry no speech; drop them rather than voicing the alt text.
_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')


def path_to_url(path):
    """Absolute filesystem path -> file:// URL (spaces and unicode percent-encoded)."""
    return 'file://' + quote(os.path.abspath(path))


def url_to_path(url):
    """file:// URL -> absolute filesystem path."""
    return unquote(urlparse(url).path)


def parse_frontmatter(text):
    """Split a chapter file into (frontmatter dict, body).

    Deliberately minimal: only top-level `key: value` scalars are read, which is
    all the pipeline needs (title, chapter, written). Block scalars such as
    `author_note: |` stay in the frontmatter and so never reach the body — the
    author's afterword is not part of the narration.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        # Only unindented `key: value` lines; indented lines belong to a block.
        km = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):[ \t]*(.*)$', line)
        if km:
            meta[km.group(1)] = km.group(2).strip()
    return meta, text[m.end():]


FILENAME_STYLES = ('dated', 'chapter')


def normalise_written(written):
    """'2023-03-09 00:07' / '2023-03-09' -> the same, validated; None if unparseable."""
    m = re.match(r'\s*(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}):(\d{2}))?', written or '')
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)}:{m.group(3)}" if m.group(2) else m.group(1)


def written_to_prefix(written, chapter):
    """'2023-03-09 00:07' + ch 500 -> '2023-03-09T0007.00500', a sortable prefix.

    No colon (illegal on the SMB share) and no underscore (sync_filesystem
    derives the chapter title by splitting the filename on the first '_').

    The trailing chapter number is a tiebreaker, not decoration: source
    timestamps are minute-resolution, so chapters posted in the same minute
    would otherwise fall back to alphabetical title order and play out of
    sequence.
    """
    tail = f".{int(chapter):05d}"
    m = re.match(r'\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})', written or '')
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}{m.group(5)}{tail}"
    m = re.match(r'\s*(\d{4})-(\d{2})-(\d{2})\s*$', written or '')
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T0000{tail}"
    return None


class MarkdownRepoScraper(BaseScraper):
    """Import chapters from a local markdown repo instead of over HTTP."""

    def __init__(self, config, output_dir='inputs', db=None):
        # BaseScraper.__init__ builds an HTTP session and requires config['latest'];
        # neither applies to a filesystem source, so set up only what is shared.
        self.series_url = config.get('url', '')
        self.current_chapter_url = config.get('latest')
        self.series_name = config['name']
        self.system_types = config.get('system', {}).get('type', [])
        self.output_dir = output_dir
        self.db = db
        self.root = url_to_path(self.series_url)
        self.filename_style = config.get('filename_style', 'dated')
        if self.filename_style not in FILENAME_STYLES:
            print(f"{YELLOW}Unknown filename_style {self.filename_style!r} for "
                  f"'{self.series_name}', using 'dated'{RESET}")
            self.filename_style = 'dated'
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _chapter_index_from_url(url):
        """Chapter number from the filename — stable across volume re-splits."""
        m = re.search(r'/(\d+)\.md$', url_to_path(url))
        return int(m.group(1)) if m else None

    def _chapter_files(self):
        """Every chapter .md under the series root, ordered by chapter number."""
        found = []
        if not os.path.isdir(self.root):
            print(f"{YELLOW}Markdown source not found: {self.root}{RESET}")
            return found
        for vol in os.listdir(self.root):
            vol_dir = os.path.join(self.root, vol)
            if not os.path.isdir(vol_dir):
                continue
            for name in os.listdir(vol_dir):
                if not name.endswith('.md') or name in ('info.md', 'codex.md'):
                    continue
                stem = name[:-3]
                if stem.isdigit():
                    found.append((int(stem), os.path.join(vol_dir, name)))
        found.sort(key=lambda t: t[0])
        return found

    def _read_chapter(self, path):
        """Return (title, content, date_label) for one chapter file, or None to skip.

        date_label is the filename prefix for the 'dated' style and the plain
        written date (or None) for the 'chapter' style.
        """
        with open(path, encoding='utf-8') as f:
            meta, body = parse_frontmatter(f.read())

        # Filename is authoritative for the chapter number; frontmatter may lag.
        stem = os.path.splitext(os.path.basename(path))[0]
        chapter = int(stem) if stem.isdigit() else meta.get('chapter')

        title = self.clean_chapter_title(meta.get('title', '').strip())
        if not title:
            print(f"{YELLOW}No title in {path}, skipping{RESET}")
            return None

        # Prefix the chapter number so titles read "Chapter 12 - Foo" in the
        # dashboard and in audiobookshelf, where the filename prefix is not shown.
        if chapter is not None:
            title = f"Chapter {chapter} - {title}"

        if self.filename_style == 'chapter':
            # Ordering rides on the chapter number, so the date is informational
            # (DB + MP3 tag) and an undated chapter is still importable.
            date_label = (normalise_written(meta.get('written'))
                          or normalise_written(meta.get('published')))
        else:
            date_label = (written_to_prefix(meta.get('written'), chapter)
                          or written_to_prefix(meta.get('published'), chapter))
            if not date_label:
                # The date prefix is what orders a 'dated' series, so an undated
                # chapter would silently land out of sequence in the audiobook.
                print(f"{YELLOW}No 'written'/'published' date in {path}, skipping{RESET}")
                return None

        content = _IMAGE_RE.sub('', body).strip()
        return title, content, date_label

    def fetch_chapter_content(self, chapter_url):
        """Read one chapter. Mirrors the HTTP scrapers' (title, content, date)."""
        parsed = self._read_chapter(url_to_path(chapter_url))
        if not parsed:
            return "Title not found", "Content not found", None
        return parsed

    def resolve_chapter_url(self, chapter_title):
        """Find a chapter file by its frontmatter title."""
        target = chapter_title.strip().lower()
        for _num, path in self._chapter_files():
            with open(path, encoding='utf-8') as f:
                meta, _ = parse_frontmatter(f.read())
            if meta.get('title', '').strip().lower() == target:
                return path_to_url(path)
        return None

    def scrape_chapters(self):
        """Import every chapter not already registered.

        Unlike the HTTP scrapers there is no next-link to follow: the whole
        series is on disk, so walk it in chapter order and let save_chapter's
        source-identity check skip what is already present. That makes the run
        idempotent and self-healing — a deleted raw .txt is re-imported onto its
        existing row rather than duplicated.
        """
        new_chapter_found = False
        last_url = self.current_chapter_url

        for num, path in self._chapter_files():
            parsed = self._read_chapter(path)
            if not parsed:
                continue
            title, content, date_label = parsed
            url = path_to_url(path)
            if self.save_chapter(title, content, date_label, source_url=url, chapter_index=num,
                                 dated_filename=self.filename_style == 'dated'):
                print(f"\n\t{title}")
                new_chapter_found = True
            last_url = url

        return last_url, new_chapter_found

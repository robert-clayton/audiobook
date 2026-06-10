"""ScribbleHub chapter scraper with CloudFlare bypass and paginated TOC date lookup."""

import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import cloudscraper
from .base import BaseScraper, ChapterUnavailableError
from ..utils.colors import PURPLE, YELLOW, RESET


class ScribbleHubScraper(BaseScraper):
    """Scraper for ScribbleHub.com web novel chapters.

    Uses cloudscraper to bypass CloudFlare protection. Resolves accurate
    publication dates and chapter ordering via paginated TOC lookups.
    """

    MAX_TOC_PAGES = 100

    def __init__(self, config, output_dir='inputs', db=None):
        super().__init__(config, output_dir, db=db)
        # Replaces the base session (and its retry adapter) — mounting a retry
        # adapter over cloudscraper's own would break the CloudFlare bypass.
        self.session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )

    def fetch_chapter_content(self, chapter_url):
        """Fetch and parse a single chapter page.

        Args:
            chapter_url: Full URL of the chapter page.

        Returns:
            Tuple of (title, content_text, published_date).

        Raises:
            ChapterUnavailableError: when the chapter returns 404 (deleted).
        """
        resp = self._get(chapter_url)
        if resp.status_code == 404:
            raise ChapterUnavailableError(f"Chapter not found (404): {chapter_url}")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        return self._parse_chapter(soup)

    def _parse_chapter(self, soup):
        """Extract (title, content_text, published_date) from a chapter page soup."""
        title_tag = soup.find('h1', class_='chapter-title') or soup.find('title')
        title = self.clean_chapter_title(title_tag.get_text(strip=True)) if title_tag else "Title not found"

        published_tag = soup.find('time')
        if published_tag and published_tag.has_attr('datetime'):
            dt = datetime.fromisoformat(published_tag['datetime'].replace('Z', '+00:00'))
            published = dt.strftime('%Y-%m-%d')
        else:
            published = 'unknown_date'

        content_div = soup.find('div', id='chp_raw')
        if content_div:
            texts = [t.strip() for t in content_div.stripped_strings if t.strip() not in self.ANTISCRAPES]
            # Remove anti-scrape messages embedded within larger text blocks
            cleaned = []
            for text in texts:
                for msg in self.ANTISCRAPES:
                    if msg in text:
                        text = text.replace(msg, '').strip()
                if text:
                    cleaned.append(text)
            content = '\n'.join(cleaned)
        else:
            content = 'Content not found'

        return title, content, published

    # ── TOC helpers ──────────────────────────────────────────────────

    def _toc_base_url(self):
        parsed = urlparse(self.series_url)
        return parsed._replace(query="").geturl()

    def _fetch_toc_page(self, page):
        """Fetch one TOC page. Returns list of (order, href, date, link_text)."""
        resp = self._get(f"{self._toc_base_url()}?toc={page}#content1")
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        entries = soup.select('ol.toc_ol li.toc_w')
        page_data = []
        for entry in entries:
            a_tag = entry.find('a', class_='toc_a')
            date_span = entry.find('span', class_='fic_date_pub')
            if a_tag and 'href' in a_tag.attrs:
                order = int(entry.get('order', -1))
                href = a_tag['href']
                date = date_span['title'] if (date_span and 'title' in date_span.attrs) else None
                page_data.append((order, href, date, a_tag.get_text(strip=True)))
        return page_data

    def get_chapter_dates_paginated(self, toc_url, target_urls):
        """Resolve publication dates for chapters via the paginated TOC.

        Fetches the first TOC page, then estimates and fetches additional pages
        as needed to find dates for all target URLs.

        Args:
            toc_url: URL of the series table-of-contents page (unused beyond
                series_url; kept for backward compatibility).
            target_urls: List of chapter URLs to look up dates for.

        Returns:
            Dict mapping chapter URL to date string (e.g. "January 1, 2025").
        """
        try:
            toc_data = self._fetch_toc_page(1)
        except Exception:
            return {}
        if not toc_data:
            return {}

        chapter_dates = {href: date for (_, href, date, _) in toc_data if date}
        href_to_order = {href: order for (order, href, _, _) in toc_data}
        orders = [order for (order, _, _, _) in toc_data]
        max_order = max(orders)
        chapters_per_page = len(orders)

        def estimate_page(order):
            return ((max_order - order) // chapters_per_page) + 1

        missing_urls = [url for url in target_urls if url not in chapter_dates]
        pages_needed = set()
        for url in missing_urls:
            order = href_to_order.get(url)
            if order is None:
                match = re.search(r'/chapter/(\d+)/', url)
                if match:
                    order = int(match.group(1))
                else:
                    continue
            page = estimate_page(order)
            if page > 1:
                pages_needed.add(page)

        for page in sorted(pages_needed):
            try:
                page_data = self._fetch_toc_page(page)
            except Exception:
                continue
            for (_, href, date, _) in page_data:
                if date:
                    chapter_dates[href] = date

        return chapter_dates

    def resolve_chapter_url(self, chapter_title):
        """Fetch the full paginated TOC and find a chapter URL by fuzzy title match.

        The TOC is cached after the first fetch so bulk resolution is efficient.
        """
        if not self.series_url:
            return None

        if not hasattr(self, '_toc_links'):
            self._toc_links = self._fetch_full_toc()

        def normalize(s):
            s = self.clean_chapter_title(s)
            s = re.sub(r'[^\w\s]', '', s.lower())
            return re.sub(r'\s+', ' ', s).strip()

        target = normalize(chapter_title)

        for link_text, url in self._toc_links:
            if normalize(link_text) == target:
                return url

        return None

    def _fetch_full_toc(self):
        """Walk all TOC pages, returning [(link_text, url), ...]."""
        links = []
        seen = set()
        for page in range(1, self.MAX_TOC_PAGES + 1):
            try:
                page_data = self._fetch_toc_page(page)
            except Exception:
                break
            fresh = [(text, href) for (_, href, _, text) in page_data
                     if href not in seen]
            if not fresh:
                # Empty page or pagination wrapped around to repeats — done
                break
            for _, href in fresh:
                seen.add(href)
            links.extend(fresh)
            if len(page_data) > len(fresh):
                break  # partial repeats: this was the last real page
        return links

    def find_next_chapter(self, soup):
        """Extract the next chapter URL from the prev/next navigation.

        Returns:
            Absolute URL of the next chapter, or None if this is the last chapter.
        """
        prenext_div = soup.find('div', class_='prenext')
        if prenext_div:
            next_link = prenext_div.find('a', class_='btn-next')
            if next_link and next_link.has_attr('href'):
                return urljoin(self.current_chapter_url, next_link['href'])
        return None

    def scrape_chapters(self):
        """Scrape chapters in a single pass, then resolve dates and save.

        Each chapter page is fetched exactly once: content and the next-chapter
        link are parsed from the same response. Publication dates and chapter
        ordering come from the paginated TOC. A visited set guards against
        next-link navigation loops.

        Returns:
            Tuple of (last_chapter_url, new_chapter_found).
        """
        new_chapter_found = False
        visited = set()
        pending = []  # (url, title, content, fallback_date)

        def norm(u):
            return u.rstrip('/').split('?')[0]

        # Phase 1: walk chapters, parsing content and next link per fetch
        while self.current_chapter_url:
            current_norm = norm(self.current_chapter_url)
            if current_norm in visited:
                print(f"\n\t{YELLOW}Navigation loop detected at {self.current_chapter_url}, "
                      f"stopping scrape{RESET}")
                break
            visited.add(current_norm)

            try:
                resp = self._get(self.current_chapter_url)
                if resp.status_code == 404:
                    raise ChapterUnavailableError(self.current_chapter_url)
                resp.raise_for_status()
            except ChapterUnavailableError:
                print(f"\n\t{YELLOW}Skipping deleted chapter: {self.current_chapter_url}{RESET}")
                break  # no nav links available from a 404 page
            soup = BeautifulSoup(resp.text, 'html.parser')

            title, content, fallback_date = self._parse_chapter(soup)
            pending.append((self.current_chapter_url, title, content, fallback_date))

            next_url = self.find_next_chapter(soup)
            if not next_url:
                break
            self.current_chapter_url = next_url

        # Phase 2: resolve accurate dates for what we found
        chapter_dates = {}
        if pending:
            chapter_dates = self.get_chapter_dates_paginated(
                self.series_url, [url for url, *_ in pending])

        # Phase 3: save
        for url, title, content, fallback_date in pending:
            if title == "Title not found":
                continue
            date = chapter_dates.get(url, fallback_date)
            saved = self.save_chapter(
                title, content, date, source_url=url,
                chapter_index=self._chapter_index_from_url(url))
            if saved:
                print(f"\n\t{PURPLE}{title}{RESET}")
                new_chapter_found = True

        return self.current_chapter_url, new_chapter_found

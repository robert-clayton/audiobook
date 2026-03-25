"""RoyalRoad chapter scraper with system message detection and speaker tagging."""

from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re
import requests
from .base import BaseScraper, ChapterUnavailableError
from ..utils.colors import PURPLE, YELLOW, RESET

def _fs_safe(s):
    """Remove filesystem-unsafe characters for comparison purposes."""
    return re.sub(r'[\/:*?"<>|]', '', s)


def _strip_rr_cruft(raw_title, series_name):
    """Strip RoyalRoad boilerplate and series name from a raw <title> string.

    Handles: "| Royal Road", bare "Royal Road" suffix, [genre tags],
    promotional prefixes like "(Book 3 Complete)", and leading series name.
    """
    title = raw_title

    # Strip " | Royal Road" or trailing " Royal Road"
    if ' | Royal Road' in title:
        title = title.split(' | Royal Road')[0].strip()
    elif title.endswith(' Royal Road'):
        title = title[:-len(' Royal Road')].strip()

    # Strip trailing [...] genre/promo tags
    title = re.sub(r'\s*\[[^\]]*\]\s*$', '', title).strip()

    # Try to split on the last " - " where the remainder contains the config
    # series name.  Scanning right-to-left avoids eating sub-titles that happen
    # to precede the series name (e.g. "Chapter 1 - Roll For Survival - DotF").
    # Also compare with filesystem-unsafe chars stripped so that a config name
    # like "ReBirth" matches a raw title containing "Re:Birth".
    sep = ' - '
    name_lower = series_name.lower()
    name_safe = _fs_safe(name_lower)
    idx = title.rfind(sep)
    while idx != -1:
        remainder = title[idx + len(sep):]
        remainder_lower = remainder.lower()
        if name_lower in remainder_lower or name_safe in _fs_safe(remainder_lower):
            title = title[:idx].strip()
            break
        idx = title.rfind(sep, 0, idx)

    # Strip leading series name prefix (some authors prefix every chapter)
    if title.lower().startswith(name_lower) or _fs_safe(title.lower()).startswith(name_safe):
        # Determine how many chars to skip from the original title.
        # If the exact name matched, skip len(series_name); otherwise find
        # the prefix length by scanning the original until we've consumed
        # enough non-unsafe chars to cover the safe name.
        if title.lower().startswith(name_lower):
            skip = len(series_name)
        else:
            consumed = 0
            skip = 0
            for ch in title:
                if consumed >= len(name_safe):
                    break
                skip += 1
                if ch not in r'\/:*?"<>|':
                    consumed += 1
        stripped = title[skip:].strip()
        if stripped:
            title = stripped

    return title


class RoyalRoadScraper(BaseScraper):
    """Scraper for RoyalRoad.com web novel chapters.

    Handles HTML parsing, system-voice tagging (bold, italic, tables, etc.),
    anti-scrape filtering, and next-chapter navigation.
    """
    def fetch_chapter_content(self, chapter_url):
        """Fetch and parse a single chapter page.

        Args:
            chapter_url: Full URL of the chapter page.

        Returns:
            Tuple of (title, content_text, published_date).
        """
        response = self.session.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title_tag = soup.find('title')
        title = self._extract_title(title_tag.get_text(strip=True)) if title_tag else "Title not found"
        title = self.clean_chapter_title(title)

        published_tag = soup.find('time')
        published_date = published_tag['datetime'] if published_tag else 'unknown_date'
        if published_tag:
            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')

        content_div = soup.find('div', class_='chapter-content')
        if not content_div:
            page_text = soup.get_text().lower()
            if 'drafted or deleted' in page_text:
                raise ChapterUnavailableError(
                    f"Chapter has been deleted or drafted: {chapter_url}")
            return title, "Content not found", published_date

        # Clean and format system messages
        content_div = self.clean_chapter_content(content_div)

        # Flatten nested div wrappers that some chapters use,
        # so <p> tags become direct children for extraction
        for div in content_div.find_all('div'):
            div.unwrap()

        seen_paragraphs = set()
        lines = []
        for element in content_div.children:
            if isinstance(element, NavigableString):
                text = str(element)
            elif hasattr(element, 'get_text'):
                text = element.get_text(separator=' ')
            else:
                continue
            normalized = re.sub(r'\s+', ' ', text).strip()
            # Clean spacing artifacts from get_text separator around inline tags
            normalized = re.sub(r" ([,.\!\?;:'\"])", r'\1', normalized)
            if not normalized or normalized in self.ANTISCRAPES or normalized in seen_paragraphs:
                continue
            # Remove anti-scrape messages embedded within larger text blocks
            for msg in self.ANTISCRAPES:
                if msg in normalized:
                    normalized = normalized.replace(msg, '').strip()
                    normalized = re.sub(r'\s+', ' ', normalized).strip()
            if not normalized:
                continue
            seen_paragraphs.add(normalized)
            lines.append(normalized)

        return title, '\n'.join(lines), published_date

    def _extract_title(self, raw_title):
        """Extract the chapter title from a RoyalRoad <title> tag.

        Handles various formats:
        - "Chapter 1 - Series Name | Royal Road"
        - "Series Name Chapter 1 - Series Name | Royal Road"  (author prefixes)
        - "Chapter 1 - (Book 3) Series Name [genre tags] Royal Road"  (promo cruft)
        """
        title = _strip_rr_cruft(raw_title, self.series_name)
        return title

    def clean_chapter_content(self, content_div):
        """Apply system-voice speaker tags to configured HTML element types.

        Processes the chapter content div in-place, wrapping matched elements
        with ``<<SPEAKER=system>>`` tags based on ``self.system_types``.

        Args:
            content_div: BeautifulSoup Tag containing chapter HTML.

        Returns:
            The modified content_div.
        """
        def wrap_system(text, speaker='system'):
            return f"<<SPEAKER={speaker}>>{text.strip()}<</SPEAKER>>"

        # 1) Remove unwanted styling
        for tag in content_div.find_all(['em', 'span']):
            style = tag.get('style', '')
            if 'font-weight: 400' in style:
                tag.replace_with(tag.get_text())

        # 2) Replace <hr> with newlines
        for hr in content_div.find_all('hr'):
            hr.replace_with('\n\n')

        # 3) Define handlers for each system type
        handlers = {
            'table': self._handle_table_system,
            'center': self._handle_center_system,
            'bold': self._handle_bold_system,
            'italic': self._handle_italic_system,
            'bracket': self._handle_bracket_system,
            'angle': self._handle_angle_system,
            'blockquote': self._handle_blockquote_system,
        }

        # 4) Run only the handlers for types in self.system_types
        for stype in self.system_types:
            handler = handlers.get(stype)
            if handler:
                handler(content_div, wrap_system)

        return content_div

    def _handle_table_system(self, div, wrap):
        """Wrap table body content with system speaker tags."""
        for table in div.find_all('table'):
            for tbody in table.find_all('tbody'):
                # collapse <br> to spaces
                for br in tbody.find_all('br'):
                    br.replace_with(' ')
                text = tbody.get_text(separator='\n', strip=True)
                tbody.replace_with(wrap(text))

    def _handle_center_system(self, div, wrap):
        """Wrap center-aligned paragraphs with system speaker tags."""
        for p in div.find_all('p', style=lambda v: v and 'text-align: center' in v):
            text = p.get_text(separator='\n', strip=True)
            p.replace_with(wrap(text))

    def _handle_bold_system(self, div, wrap):
        """Wrap bold/strong text with system speaker tags."""
        for strong in div.find_all(['strong', 'b']):
            text = re.sub(r'\s+', ' ', strong.get_text()).strip()
            strong.replace_with(wrap(text))

    def _handle_italic_system(self, div, wrap):
        """Wrap italic/em text with system speaker tags."""
        for em in div.find_all('em'):
            text = re.sub(r'\s+', ' ', em.get_text()).strip()
            em.replace_with(wrap(text))

    def _handle_bracket_system(self, div, wrap):
        """Wrap [bracketed] text with system or fable speaker tags."""
        for node in div.find_all(string=re.compile(r'\[.*?\]')):
            speaker = 'fable' if node.parent.name in ('em', 'i') else 'system'
            clean = node.strip('[]').strip()
            node.replace_with(wrap(clean, speaker))

    def _handle_angle_system(self, div, wrap):
        """Wrap <angle-bracketed> or <<double-angle>> text with speaker tags."""
        # Matches either <<inner>> or <inner>
        pattern = re.compile(r'<<([^<>]+)>>|<([^<>]+)>')
        for node in div.find_all(string=pattern):
            def repl(m):
                # m.group(1) is for <<…>>, m.group(2) for <…>
                inner = m.group(1) or m.group(2)
                speaker = 'fable' if node.parent.name in ('em', 'i') else 'system'
                return wrap(inner, speaker)
            new_text = pattern.sub(repl, node)
            node.replace_with(new_text)

    def _handle_blockquote_system(self, div, wrap):
        """Wrap blockquote content with system speaker tags."""
        for blockquote in div.find_all('blockquote'):
            text = re.sub(r'\s+', ' ', blockquote.get_text()).strip()
            blockquote.replace_with(wrap(text))

    def resolve_chapter_url(self, chapter_title):
        """Fetch the series TOC page and find a chapter URL by fuzzy title match.

        The TOC is cached after the first fetch so bulk resolution is efficient.
        """
        if not self.series_url:
            return None

        if not hasattr(self, '_toc_links'):
            try:
                response = self.session.get(self.series_url)
                response.raise_for_status()
            except Exception:
                self._toc_links = []
                return None
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', id='chapters')
            self._toc_links = []
            if table:
                for a in table.find_all('a', href=True):
                    link_text = a.get_text(strip=True)
                    if link_text:
                        self._toc_links.append((
                            link_text,
                            requests.compat.urljoin(self.series_url, a['href']),
                        ))

        def normalize(s):
            s = _strip_rr_cruft(s, self.series_name)
            s = self.clean_chapter_title(s)
            s = re.sub(r'[^\w\s]', '', s.lower())
            return re.sub(r'\s+', ' ', s).strip()

        target = normalize(chapter_title)

        for link_text, url in self._toc_links:
            if normalize(link_text) == target:
                return url

        return None

    def _ensure_toc_links(self):
        """Fetch and cache the TOC chapter link list (reuses resolve_chapter_url cache)."""
        if not hasattr(self, '_toc_links'):
            # Trigger TOC fetch via resolve_chapter_url with a dummy title
            self.resolve_chapter_url('')

    def _find_next_from_toc(self, current_url):
        """Find the next chapter URL after current_url using the cached TOC.

        Returns:
            The next chapter URL, or None if not found.
        """
        self._ensure_toc_links()
        if not self._toc_links:
            return None

        # Normalize URLs for comparison (strip trailing slashes, query params)
        def norm(u):
            return u.rstrip('/').split('?')[0]

        current_norm = norm(current_url)
        for i, (_, url) in enumerate(self._toc_links):
            if norm(url) == current_norm and i + 1 < len(self._toc_links):
                return self._toc_links[i + 1][1]
        return None

    def find_next_chapter(self, soup):
        """Extract the next chapter URL from the navigation buttons.

        Returns:
            Absolute URL of the next chapter, or None if this is the last chapter.
        """
        nav = soup.find('div', class_='row nav-buttons')
        if nav:
            for a in nav.find_all('a', class_='btn btn-primary col-xs-12'):
                if 'Next' in a.text and 'href' in a.attrs:
                    return requests.compat.urljoin(self.current_chapter_url, a['href'])
        return None

    def scrape_chapters(self):
        """Scrape chapters sequentially from current URL, following next-chapter links.

        Returns:
            Tuple of (last_chapter_url, new_chapter_found).
        """
        new_chapter_found = False
        while self.current_chapter_url:
            try:
                title, content, date = self.fetch_chapter_content(self.current_chapter_url)
            except ChapterUnavailableError:
                print(f"\n\t{YELLOW}Skipping deleted/drafted chapter: {self.current_chapter_url}{RESET}")
                # Still try to find next chapter link from the page
                soup = BeautifulSoup(self.session.get(self.current_chapter_url).content, 'html.parser')
                next_chapter = self.find_next_chapter(soup)
                if not next_chapter:
                    return self.current_chapter_url, new_chapter_found
                self.current_chapter_url = next_chapter
                continue
            except requests.exceptions.HTTPError as e:
                print(f"\n\t{YELLOW}HTTP {e.response.status_code} for chapter: {self.current_chapter_url}{RESET}")
                # Can't get nav links from a failed page, fall back to TOC
                next_chapter = self._find_next_from_toc(self.current_chapter_url)
                if not next_chapter:
                    print(f"\t{YELLOW}No next chapter found in TOC, stopping scrape{RESET}")
                    return self.current_chapter_url, new_chapter_found
                self.current_chapter_url = next_chapter
                continue

            if title != "Title not found" and self.save_chapter(title, content, date, source_url=self.current_chapter_url):
                print(f"\n\t{PURPLE}{title}{RESET}")
                new_chapter_found = True

            soup = BeautifulSoup(self.session.get(self.current_chapter_url).content, 'html.parser')
            next_chapter = self.find_next_chapter(soup)
            if not next_chapter:
                return self.current_chapter_url, new_chapter_found
            self.current_chapter_url = next_chapter

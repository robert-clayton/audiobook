"""RoyalRoad chapter scraper with system message detection and speaker tagging."""

from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re
import requests
from .base import BaseScraper
from ..utils.colors import PURPLE, RESET

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
        title = title_tag.get_text(strip=True).split(f' - {self.series_name}')[0] if title_tag else "Title not found"
        title = self.clean_chapter_title(title)

        published_tag = soup.find('time')
        published_date = published_tag['datetime'] if published_tag else 'unknown_date'
        if published_tag:
            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')

        content_div = soup.find('div', class_='chapter-content')
        if not content_div:
            return title, "Content not found", published_date

        # Clean and format system messages
        content_div = self.clean_chapter_content(content_div)

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
            seen_paragraphs.add(normalized)
            lines.append(normalized)

        return title, '\n'.join(lines), published_date

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
            title, content, date = self.fetch_chapter_content(self.current_chapter_url)
            if title != "Title not found" and self.save_chapter(title, content, date):
                print(f"\n\t{PURPLE}{title}{RESET}")
                new_chapter_found = True

            soup = BeautifulSoup(self.session.get(self.current_chapter_url).content, 'html.parser')
            next_chapter = self.find_next_chapter(soup)
            if not next_chapter:
                return self.current_chapter_url, new_chapter_found
            self.current_chapter_url = next_chapter

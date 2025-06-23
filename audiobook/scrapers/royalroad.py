from bs4 import BeautifulSoup
from datetime import datetime
import re
import requests
from .base import BaseScraper
from ..utils.colors import PURPLE, RESET

class RoyalRoadScraper(BaseScraper):
    def fetch_chapter_content(self, chapter_url):
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

        seen_lines = set()
        lines = []
        for text in content_div.stripped_strings:
            normalized = re.sub(r'\s+', ' ', text).strip()
            if normalized in seen_lines or normalized in self.ANTISCRAPES:
                continue
            seen_lines.add(normalized)
            lines.append(normalized)

        return title, '\n'.join(lines), published_date

    def clean_chapter_content(self, content_div):
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
        }

        # 4) Run only the handlers for types in self.system_types
        for stype in self.system_types:
            handler = handlers.get(stype)
            if handler:
                handler(content_div, wrap_system)

        return content_div

    def _handle_table_system(self, div, wrap):
        for table in div.find_all('table'):
            for tbody in table.find_all('tbody'):
                # collapse <br> to spaces
                for br in tbody.find_all('br'):
                    br.replace_with(' ')
                text = tbody.get_text(separator='\n', strip=True)
                tbody.replace_with(wrap(text))

    def _handle_center_system(self, div, wrap):
        for p in div.find_all('p', style=lambda v: v and 'text-align: center' in v):
            text = p.get_text(separator='\n', strip=True)
            p.replace_with(wrap(text))

    def _handle_bold_system(self, div, wrap):
        for strong in div.find_all('strong'):
            text = re.sub(r'\s+', ' ', strong.get_text()).strip()
            strong.replace_with(wrap(text))

    def _handle_italic_system(self, div, wrap):
        for em in div.find_all('em'):
            text = re.sub(r'\s+', ' ', em.get_text()).strip()
            em.replace_with(wrap(text))

    def _handle_bracket_system(self, div, wrap):
        for node in div.find_all(string=re.compile(r'\[.*?\]')):
            speaker = 'fable' if node.parent.name in ('em', 'i') else 'system'
            clean = node.strip('[]').strip()
            node.replace_with(wrap(clean, speaker))

    def _handle_angle_system(self, div, wrap):
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

    def find_next_chapter(self, soup):
        nav = soup.find('div', class_='row nav-buttons')
        if nav:
            for a in nav.find_all('a', class_='btn btn-primary col-xs-12'):
                if 'Next' in a.text and 'href' in a.attrs:
                    return requests.compat.urljoin(self.current_chapter_url, a['href'])
        return None

    def scrape_chapters(self):
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

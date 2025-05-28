from bs4 import BeautifulSoup
from datetime import datetime
import re
import requests
from .base import BaseScraper
from ..utils.colors import GREEN, YELLOW, PURPLE, RESET

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

        seen_lines = set()
        lines = []
        for text in content_div.stripped_strings:
            normalized = re.sub(r'\s+', ' ', text).strip()
            if normalized in seen_lines or normalized in self.ANTISCRAPES:
                continue
            seen_lines.add(normalized)
            lines.append(normalized)
        return title, '\n'.join(lines), published_date

    def find_next_chapter(self, soup):
        nav = soup.find('div', class_='row nav-buttons')
        if nav:
            for a in nav.find_all('a', class_='btn btn-primary col-xs-12'):
                if 'Next' in a.text and 'href' in a.attrs:
                    return requests.compat.urljoin(self.current_chapter_url, a['href'])
        return None

    def scrape_chapters(self):
        new_chapter_found = False
        try:
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
        except KeyboardInterrupt:
            print(f"{YELLOW}Scraping interrupted.{RESET}")
            return self.current_chapter_url, new_chapter_found

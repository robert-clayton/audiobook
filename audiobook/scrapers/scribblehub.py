import time
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import cloudscraper
from .base import BaseScraper
from ..utils.colors import PURPLE, RESET

class ScribbleHubScraper(BaseScraper):
    POLITE_DELAY = 1.0

    def __init__(self, config):
        super().__init__(config)
        self.session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )

    def fetch_chapter_content(self, chapter_url):
        resp = self.session.get(chapter_url)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

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
            content = '\n'.join(texts)
        else:
            content = 'Content not found'

        return title, content, published

    def get_chapter_dates_paginated(self, toc_url, target_urls):
        def fetch_page(toc_page_url):
            resp = self.session.get(toc_page_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            entries = soup.select('ol.toc_ol li.toc_w')
            page_data = []
            for entry in entries:
                a_tag = entry.find('a', class_='toc_a')
                date_span = entry.find('span', class_='fic_date_pub')
                if a_tag and date_span and 'href' in a_tag.attrs and 'title' in date_span.attrs:
                    order = int(entry.get('order', -1))
                    href = a_tag['href']
                    title = date_span['title']
                    page_data.append((order, href, title))
            return page_data

        toc_data = fetch_page(toc_url)
        if not toc_data:
            return {}

        chapter_dates = {href: date for (_, href, date) in toc_data}
        href_to_order = {href: order for (order, href, _) in toc_data}
        orders = [order for (order, _, _) in toc_data]
        max_order = max(orders)
        chapters_per_page = len(orders)

        def estimate_page(order): return ((max_order - order) // chapters_per_page) + 1

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
            pages_needed.add(page)

        parsed = urlparse(toc_url)
        base_url = parsed._replace(query="").geturl()

        for page in sorted(pages_needed):
            toc_page_url = f"{base_url}?toc={page}#content1"
            print(f"{PURPLE}[DEBUG] Fetching ToC page {page}{RESET}")
            page_data = fetch_page(toc_page_url)
            for (_, href, date) in page_data:
                chapter_dates[href] = date

        return chapter_dates

    def find_next_chapter(self, soup):
        prenext_div = soup.find('div', class_='prenext')
        if prenext_div:
            next_link = prenext_div.find('a', class_='btn-next')
            if next_link and next_link.has_attr('href'):
                return urljoin(self.current_chapter_url, next_link['href'])
        return None

    def scrape_chapters(self):
        print(f"Starting the scraping process for {self.series_name}")
        last = None
        chapter_urls = []

        # Phase 1: Collect URLs
        try:
            url = self.current_chapter_url
            while url:
                chapter_urls.append(url)
                resp = self.session.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, 'html.parser')
                url = self.find_next_chapter(soup)
        except KeyboardInterrupt:
            print("Scraping interrupted during URL collection!")
            return last

        print(f"{PURPLE}[DEBUG] Collected {len(chapter_urls)} chapter URLs{RESET}")

        # Phase 2: Fetch dates
        toc_url = self.series_url  # Provided by config
        chapter_dates = self.get_chapter_dates_paginated(toc_url, chapter_urls)

        # Phase 3: Scrape content
        try:
            for url in chapter_urls:
                print(f"{PURPLE}[DEBUG] Scraping: {url}{RESET}")
                title, content, fallback_date = self.fetch_chapter_content(url)
                date = chapter_dates.get(url, fallback_date)

                if title != "Title not found":
                    saved = self.save_chapter(title, content, date)
                    print(f"{PURPLE}[DEBUG] Saved status: {saved}{RESET}")
                    if saved:
                        print(f"\t{title}")

                last = url
                print(f"{PURPLE}[DEBUG] Sleeping for {self.POLITE_DELAY} seconds")
                time.sleep(self.POLITE_DELAY)

        except KeyboardInterrupt:
            print("Scraping interrupted!")
            return last

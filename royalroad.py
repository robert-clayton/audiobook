import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime

class RoyalRoadScraper:
    def __init__(self, start_chapter_url):
        self.current_chapter_url = start_chapter_url
        self.session = requests.Session()
        self.series_name = None  # Will be determined from the page title
        self.output_dir = 'inputs'

    def fetch_chapter_content(self, chapter_url):
        print(f"Fetching content from {chapter_url}...")
        response = self.session.get(chapter_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract page title to determine series name and chapter title
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text(strip=True)
            # Extract series name and chapter title from the page title
            title_match = re.match(r'^(.*?Chapter \d+)\s*-\s*([^|]+?)\s*\| Royal Road$', page_title)
            if title_match:
                title = title_match.group(1).strip()
                self.series_name = title_match.group(2).strip()

                # Check if title starts with the series name and remove it
                if title.startswith(self.series_name):
                    title = title[len(self.series_name):].strip()
            else:
                title = 'Title not found'
        else:
            title = 'Title not found'

        # Extract published datetime
        published_time_tag = soup.find('time')
        if published_time_tag:
            published_datetime_str = published_time_tag['datetime']
            published_datetime = datetime.fromisoformat(published_datetime_str.replace('Z', '+00:00'))
            published_datetime_formatted = published_datetime.strftime('%Y-%m-%d')
        else:
            published_datetime_formatted = 'unknown_date'

        # Extract and clean chapter content
        content_div = soup.find('div', class_='chapter-content')
        if content_div:
            paragraphs = content_div.find_all(['p', 'div', 'span'])  # Include tags used for paragraphs and text
            # Join text content from each paragraph element, preserving formatting
            content = '\n\n'.join(p.get_text(separator=' ', strip=True) for p in paragraphs)
            lines = content.split('\n')
            if len(lines) > 2:
                content = '\n'.join(lines[2:])
            else:
                content = 'Content not found'
        else:
            content = 'Content not found'

        return title, content, published_datetime_formatted

    def save_chapter(self, title, content, published_datetime):
        # Sanitize the title for use in filenames
        safe_title = re.sub(r'[\/:*?"<>|]', '', title)
        file_path = os.path.join(self.output_dir, self.series_name, f"{published_datetime}_{safe_title}.txt")

        os.makedirs(os.path.join(self.output_dir, self.series_name), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        print(f"Chapter '{title}' saved to {file_path}")

    def find_next_chapter(self, soup):
        # Look for the "Next Chapter" button/link
        nav_buttons = soup.find('div', class_='row nav-buttons')
        if nav_buttons:
            for button in nav_buttons.find_all('a', class_='btn btn-primary col-xs-12'):
                if 'Next' in button.get_text(strip=True):
                    if 'href' in button.attrs:
                        next_chapter_url = button['href']
                        return requests.compat.urljoin(self.current_chapter_url, next_chapter_url)
        return None

    def scrape_chapters(self):
        print("Starting the scraping process...")
        while self.current_chapter_url:
            title, content, published_datetime = self.fetch_chapter_content(self.current_chapter_url)
            self.save_chapter(title, content, published_datetime)

            response = self.session.get(self.current_chapter_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            self.current_chapter_url = self.find_next_chapter(soup)
            if self.current_chapter_url:
                print(f"Moving to next chapter: {self.current_chapter_url}")
            else:
                print("No more chapters found.")
                break

def main():
    start_chapter_url = input("Enter the URL of the starting chapter: ")
    scraper = RoyalRoadScraper(start_chapter_url=start_chapter_url)
    scraper.scrape_chapters()

if __name__ == "__main__":
    main()

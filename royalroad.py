import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime

antiscrapes = [
    "The genuine version of this novel can be found on another site. Support the author by reading it there.",
    "Love this story? Find the genuine version on the author's preferred platform and support their work!",
    "Love what you're reading? Discover and support the author on the platform they originally published on.",
    "Enjoying this book? Seek out the original to ensure the author gets credit.",
    "Support the creativity of authors by visiting the original site for this novel and more.",
    "Support the author by searching for the original publication of this novel.",
    "Ensure your favorite authors get the support they deserve. Read this novel on the original website.",
    "Unauthorized duplication: this narrative has been taken without consent. Report sightings.",
    "Unauthorized duplication: this tale has been taken without consent. Report sightings.",
    "You might be reading a pirated copy. Look for the official release to support the author.",
    "Find this and other great novels on the author's preferred platform. Support original creators!",
    "This book is hosted on another platform. Read the official version and support the author's work.",
    "This book's true home is on another platform. Check it out there for the real experience.",
    "This story has been taken without authorization. Report any sightings.",
    "This story is posted elsewhere by the author. Help them out by reading the authentic version.",
    "This story originates from a different website. Ensure the author gets the support they deserve by reading it there.",
    "This novel's true home is a different platform. Support the author by finding it there.",
    "This novel is published on a different platform. Support the original author by finding the official source.",
    "The narrative has been taken without permission. Report any sightings.",
    "Reading on this site? This novel is published elsewhere. Support the author by seeking out the original.",
]

class RoyalRoadScraper:
    def __init__(self, start_chapter_url):
        self.current_chapter_url = start_chapter_url
        self.session = requests.Session()
        self.series_name = None  # Will be determined from the page title
        self.output_dir = 'inputs'
    
    def clean_chapter_content(self, content_div):
        # Remove or replace specific HTML tags or styles
        for tag in content_div.find_all(['em', 'span']):
            if 'style' in tag.attrs and ('font-weight: 400' in tag['style']):
                tag.replace_with(tag.get_text())  # Replace with just the text content

        return content_div

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
            content_div = self.clean_chapter_content(content_div)
            paragraphs = content_div.find_all(['p', 'div', 'span'])

            # Clean and filter text content
            seen_lines = set()
            lines = []
            total_content_length = 0

            for p in paragraphs:
                text = p.get_text(separator=' ', strip=True)

                # Normalize text by removing extra spaces, line breaks, etc.
                normalized_text = re.sub(r'\s+', ' ', text).strip()
                
                if text in seen_lines:
                    continue
                if len(text) > 10000:
                    continue
                if "on Amazon" in text or "Royal Road" in text:
                    continue
                if text in antiscrapes:
                    continue
                lines.append(text)
                seen_lines.add(text)

            # Join lines with a single newline
            content = '\n'.join(lines)
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
            if title != "Title not found":
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

import os
import re
import requests
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    ANTISCRAPES = [
        "Did you know this text is from a different site? Read the official version to support the creator.",
        "The genuine version of this novel can be found on another site. Support the author by reading it there.",
        "Love this story? Find the genuine version on the author's preferred platform and support their work!",
        "Love what you're reading? Discover and support the author on the platform they originally published on.",
        "Enjoying this book? Seek out the original to ensure the author gets credit.",
        "Support the creativity of authors by visiting the original site for this novel and more.",
        "Support the author by searching for the original publication of this novel.",
        "Help support creative writers by finding and reading their stories on the original site.",
        "Ensure your favorite authors get the support they deserve. Read this novel on the original website.",
        "Unauthorized duplication: this narrative has been taken without consent. Report sightings.",
        "Unauthorized duplication: this tale has been taken without consent. Report sightings.",
        "Unauthorized reproduction: this story has been taken without approval. Report sightings.",
        "You might be reading a pirated copy. Look for the official release to support the author.",
        "You could be reading stolen content. Head to the original site for the genuine story.",
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
        "Love what you're reading? Discover and support the author on the platform they originally published on.",
        "Stolen novel; please report.",
        "Stolen story; please report.",
        "Enjoying the story? Show your support by reading it on the official site."
    ]

    def __init__(self, config):
        self.current_chapter_url = config['latest']
        self.series_url = config.get('url', '')
        self.session = requests.Session()
        self.series_name = config['name']
        self.system_types = config.get('system', {}).get('type', [])
        self.output_dir = 'inputs'

    def clean_chapter_title(self, title):
        # Unicode normalization & replacements
        normalized = title
        replacements = {
            "\xa0": " ", 
            "´": "'", 
            "ä": "ae", 
            " ́": "'", 
            "ā": "aa", 
            "é": "e",
            "ö": "oo", 
            "ū": "uu", 
            '"': "'", 
            "…": "...", 
            "—": "-", 
            "–": "-",
            "’": "'", 
            "‘": "'", 
            "`": "'", 
            "“": "'", 
            "”": "'", 
            "\t": " ",
            "~": "-", 
            ":": "", 
            "û": "uu", 
            "ú": "uu", 
            "ü": "uu", 
            "ô": "oo",
            "ó": "oo", 
            "ò": "oo", 
            "ñ": "nn", 
            "í": "ii", 
            "ì": "ii", 
            "î": "ii",
            "ç": "c", 
            "ß": "ss",
        }
        for k, v in replacements.items():
            normalized = normalized.replace(k, v)
        return normalized

    def save_chapter(self, title, content, published_date):
        safe_title = re.sub(r'[\/:*?"<>|]', '', title)
        file_path = os.path.join(self.output_dir, self.series_name, f"{published_date}_{safe_title}.txt")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path):
            return False
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    @abstractmethod
    def scrape_chapters(self):
        pass

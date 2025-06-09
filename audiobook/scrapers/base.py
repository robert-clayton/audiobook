import os
import re
import requests
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    ANTISCRAPES = [
        "A case of literary theft: this tale is not rightfully on Amazon; if you see it, report the violation.",
        "A case of theft: this story is not rightfully on Amazon; if you spot it, report the violation.",
        "Did you know this text is from a different site? Read the official version to support the creator.",
        "Did you know this story is from Royal Road? Read the official version for free and support the author.",
        "The genuine version of this novel can be found on another site. Support the author by reading it there.",
        "Love this story? Find the genuine version on the author's preferred platform and support their work!",
        "Love what you're reading? Discover and support the author on the platform they originally published on.",
        "Enjoying this book? Seek out the original to ensure the author gets credit.",
        "Support the creativity of authors by visiting the original site for this novel and more.",
        "Support the author by searching for the original publication of this novel.",
        "Support the creativity of authors by visiting Royal Road for this novel and more.",
        "Support creative writers by reading their stories on Royal Road, not stolen versions.",
        "Stolen content warning: this tale belongs on Royal Road. Report any occurrences elsewhere.",
        "Stolen content warning: this content belongs on Royal Road. Report any occurrences.",
        "Stolen content alert: this content belongs on Royal Road. Report any occurrences.",
        "Illicit content alert: this content belongs on Royal Road. Report any occurrences.",
        "Stolen from its rightful place, this narrative is not meant to be on Amazon; report any sightings.",
        "Stolen from its original source, this story is not meant to be on Amazon; report any sightings.",
        "Stolen from Royal Road, this story should be reported if encountered on Amazon.",
        "Stolen from its rightful author, this tale is not meant to be on Amazon; report any sightings.",
        "Help support creative writers by finding and reading their stories on the original site.",
        "Ensure your favorite authors get the support they deserve. Read this novel on the original website.",
        "Ensure your favorite authors get the support they deserve. Read this novel on Royal Road.",
        "Unauthorized duplication: this narrative has been taken without consent. Report sightings.",
        "Unauthorized duplication: this tale has been taken without consent. Report sightings.",
        "Unauthorized reproduction: this story has been taken without approval. Report sightings.",
        "Unauthorized usage: this narrative is on Amazon without the author's consent. Report any sightings.",
        "Unauthorized usage: this tale is on Amazon without the author's consent. Report any sightings.",
        "Unauthorized content usage: if you discover this narrative on Amazon, report the violation.",
        "Unauthorized use of content: if you find this story on Amazon, report the violation.",
        "Unauthorized use: this story is on Amazon without permission from the author. Report any sightings.",
        "Unlawfully taken from Royal Road, this story should be reported if seen on Amazon.",
        "Unauthorized tale usage: if you spot this story on Amazon, report the violation.",
        "You might be reading a pirated copy. Look for the official release to support the author.",
        "You might be reading a stolen copy. Visit Royal Road for the authentic version.",
        "You could be reading stolen content. Head to the original site for the genuine story.",
        "You could be reading stolen content. Head to Royal Road for the genuine story.",
        "Find this and other great novels on the author's preferred platform. Support original creators!",
        "Taken from Royal Road, this narrative should be reported if found on Amazon.",
        "This book is hosted on another platform. Read the official version and support the author's work.",
        "This book was originally published on Royal Road. Check it out there for the real experience.",
        "This book's true home is on another platform. Check it out there for the real experience.",
        "This story has been taken without authorization. Report any sightings.",
        "This story has been stolen from Royal Road. If you read it on Amazon, please report it",
        "This story originates from Royal Road. Ensure the author gets the support they deserve by reading it there.",
        "This story is posted elsewhere by the author. Help them out by reading the authentic version.",
        "This story originates from a different website. Ensure the author gets the support they deserve by reading it there.",
        "The story has been stolen; if detected on Amazon, report the violation.",
        "The story has been taken without consent; if you see it on Amazon, report the incident."
        "The author's content has been appropriated; report any instances of this story on Amazon.",
        "The author's narrative has been misappropriated; report any instances of this story on Amazon.",
        "The author's tale has been misappropriated; report any instances of this story on Amazon.",
        "This novel's true home is a different platform. Support the author by finding it there.",
        "This novel is published on a different platform. Support the original author by finding the official source.",
        "This story has been unlawfully obtained without the author's consent. Report any appearances on Amazon.",
        "The tale has been stolen; if detected on Amazon, report the violation.",
        "The tale has been taken without authorization; if you see it on Amazon, report the incident.",
        "This tale has been unlawfully lifted without the author's consent. Report any appearances on Amazon.",
        "This tale has been unlawfully lifted from Royal Road; report any instances of this story if found elsewhere.",
        "This tale has been pilfered from Royal Road. If found on Amazon, kindly file a report.",
        "This tale has been unlawfully obtained from Royal Road. If you discover it on Amazon, kindly report it.",
        "This tale has been unlawfully lifted from Royal Road. If you spot it on Amazon, please report it.",
        "The tale has been illicitly lifted; should you spot it on Amazon, report the violation.",
        "This text was taken from Royal Road. Help the author by reading the original version there.",
        "The narrative has been taken without permission. Report any sightings.",
        "The narrative has been stolen; if detected on Amazon, report the infringement.",
        "The narrative has been taken without authorization; if you see it on Amazon, report the incident.",
        "The narrative has been stolen; if detected on Amazon, report the infringement.",
        "The narrative has been illicitly obtained; should you discover it on Amazon, report the violation.",
        "This narrative has been unlawfully taken from Royal Road. If you see it on Amazon, please report it.",
        "This narrative has been purloined without the author's approval. Report any appearances on Amazon.",
        "This content has been unlawfully taken from Royal Road; report any instances of this story if found elsewhere.",
        "This content has been misappropriated from Royal Road; report any instances of this story if found elsewhere.",
        "A case of content theft: this narrative is not rightfully on Amazon; if you spot it, report the violation.",
        "Reading on this site? This novel is published elsewhere. Support the author by seeking out the original.",
        "Reading on Amazon or a pirate site? This novel is from Royal Road. Support the author by reading it there.",
        "Royal Road is the home of this novel. Visit there to read the original and support the author.",
        "Love what you're reading? Discover and support the author on the platform they originally published on.",
        "Stolen novel; please report.",
        "Stolen story; please report.",
        "Love this novel? Read it on Royal Road to ensure the author gets credit.",
        "If you encounter this tale on Amazon, note that it's taken without the author's consent. Report it.",
        "If you spot this tale on Amazon, know that it has been stolen. Report the violation.",
        "If you spot this narrative on Amazon, know that it has been stolen. Report the violation.",
        "If you spot this story on Amazon, know that it has been stolen. Report the violation.",
        "If you come across this story on Amazon, it's taken without permission from the author. Report it.",
        "If you come across this story on Amazon, be aware that it has been stolen from Royal Road. Please report it.",
        "If you stumble upon this tale on Amazon, it's taken without the author's consent. Report it.",
        "If you stumble upon this narrative on Amazon, it's taken without the author's consent. Report it.",
        "If you stumble upon this narrative on Amazon, be aware that it has been stolen from Royal Road. Please report it.",
        "If you find this story on Amazon, be aware that it has been stolen. Please report the infringement.",
        "If you encounter this narrative on Amazon, note that it's taken without the author's consent. Report it.",
        "If you encounter this story on Amazon, note that it's taken without permission from the author. Report it.",
        "If you discover this tale on Amazon, be aware that it has been unlawfully taken from Royal Road. Please report it.",
        "If you discover this narrative on Amazon, be aware that it has been stolen. Please report the violation.",
        "If you discover this tale on Amazon, be aware that it has been stolen. Please report the violation.",
        "Enjoying the story? Show your support by reading it on the official site.",
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

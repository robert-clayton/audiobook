import argparse
import warnings
import os
import shutil
from urllib.parse import urlparse
from .config import load_config, save_config
from .scrapers.royalroad import RoyalRoadScraper
from .scrapers.scribblehub import ScribbleHubScraper
from .processors.processing import process_series
from .utils.colors import GREEN, PURPLE, YELLOW, RESET
from requests.exceptions import HTTPError

# Map domain keywords to scraper classes
SCRAPER_MAP = {
    "royalroad.com": RoyalRoadScraper,
    "scribblehub.com": ScribbleHubScraper,
}

def detect_source_from_url(url):
    domain = urlparse(url).netloc.lower()
    for key, scraper_cls in SCRAPER_MAP.items():
        if key in domain:
            return scraper_cls
    return None

def main():
    parser = argparse.ArgumentParser(description='Convert text to speech and adjust playback speed for all series in the inputs folder.')
    parser.add_argument('--speed', type=float, default=1.0, help="Playback speed adjustment (e.g., 1.2 for 20\\% \\faster).")
    parser.add_argument('--dev', action='store_true', help='Set if testing a new dev feature.')
    args = parser.parse_args()

    config_file = 'config_dev.yml' if args.dev else 'config.yml'
    config = load_config(config_file)

    terminal_width = shutil.get_terminal_size(fallback=(80, 20)).columns
    new_chapter_found = False
    try:
        total = sum(1 for series in config['series'] if series.get('enabled', True))
        if total == 0:
            print(f"{YELLOW}No enabled series found in the configuration.{RESET}")
            return
        skipped = 0
        for idx, series in enumerate(config['series']):
            if not series.get('enabled', True):
                skipped += 1
                continue

            url = series.get("url", "")
            scraper_cls = detect_source_from_url(url)

            if not scraper_cls:
                print(f"{YELLOW}Could not determine scraper for URL: {url}. Skipping '{series.get('name', 'Unnamed')}'...{RESET}")
                continue

            scraper = scraper_cls(series)

            try:
                msg = f"{GREEN}[{idx+1-skipped}/{total}] Scraping {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                padding = max(0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET))
                print(f"\r{msg}{' ' * padding}", end='', flush=True)
                series['latest'], new_series_chapter_found = scraper.scrape_chapters()
                if new_series_chapter_found:
                    new_chapter_found = True
            except HTTPError as e:
                if e.response.status_code == 429:
                    print(f"Skipping series due to rate limiting (HTTP 429): {series['name']}")
                    continue
                else:
                    raise
            except Exception as e:
                print(f"An unexpected error occurred for '{series.get('name', 'Unnamed')}': {e}")
                continue
        if not new_chapter_found:
            msg = f"{GREEN}Scraping Complete - No New Chapters!{RESET}"
            padding = max(0, terminal_width - len(msg) + len(GREEN) + len(RESET))
            print(f"\r{msg}{' ' * padding}", end='', flush=True)
        print()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            tmp = 'tmp'
            out = config['config']['output_dir']
            
            if not os.path.exists(tmp):
                os.makedirs(tmp)
            if not os.path.exists(out):
                os.makedirs(out)

            skipped = 0
            for idx, series in enumerate(config['series']):
                if not series.get('enabled', True):
                    skipped += 1
                    continue
                msg = f"{GREEN}[{idx+1-skipped}/{total}] Generating {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                padding = max(0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET))
                print(f"\r{msg}{' ' * padding}", end='', flush=True)
                process_series('inputs', series, out, tmp, args.speed)
        print()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Scraping interrupted. Updating the latest chapter info...{RESET}")
    finally:
        save_config(config_file, config)

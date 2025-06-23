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

# Mapping of domain substrings to the corresponding scraper class
SCRAPER_MAP = {
    "royalroad.com": RoyalRoadScraper,
    "scribblehub.com": ScribbleHubScraper,
}

def detect_source_from_url(url):
    """
    Determine which scraper to use based on the URL's domain.
    Returns the scraper class or None if no match.
    """
    domain = urlparse(url).netloc.lower()
    for key, scraper_cls in SCRAPER_MAP.items():
        if key in domain:
            return scraper_cls
    return None


def main():
    """
    CLI entry point:
    - Parses arguments
    - Loads configuration
    - Scrapes new chapters for each series
    - Processes text-to-speech and audio pipeline
    """
    # Argument parsing
    parser = argparse.ArgumentParser(
        description='Convert text to speech and adjust playback speed for all series in the inputs folder.'
    )
    parser.add_argument(
        '--speed', type=float, default=1.0,
        help="Playback speed multiplier (e.g., 1.2 for 20% faster)."
    )
    parser.add_argument(
        '--dev', action='store_true',
        help='Use the development config file (config_dev.yml).'
    )
    args = parser.parse_args()

    # Choose config file based on dev flag, then load it
    config_file = 'config_dev.yml' if args.dev else 'config.yml'
    config = load_config(config_file)
    raws_subdir = "raws"

    # Determine terminal width for clean in-place printing
    terminal_width = shutil.get_terminal_size(fallback=(80, 20)).columns
    new_chapter_found = False
    try:
        # Count how many series are enabled in the config
        total = sum(1 for s in config['series'] if s.get('enabled', True))
        if total == 0:
            print(f"{YELLOW}No enabled series found in the configuration.{RESET}")
            return

        skipped = 0
        # Phase 1: Scrape new chapters
        for idx, series in enumerate(config['series']):
            if not series.get('enabled', True):
                skipped += 1
                continue

            url = series.get('url', '')
            scraper_cls = detect_source_from_url(url)

            if not scraper_cls:
                print(
                    f"{YELLOW}Could not determine scraper for URL: {url}. "
                    f"Skipping '{series.get('name', 'Unnamed')}'...{RESET}"
                )
                continue

            # Initialize scraper with series config and output directory
            output_dir = os.path.join(config['config']['output_dir'], series.get('name'), raws_subdir)
            scraper = scraper_cls(series, output_dir)
            try:
                # Prepare status message and pad to clear line
                msg = (
                    f"{GREEN}[{idx+1-skipped}/{total}] "
                    f"Scraping {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                )
                padding = max(
                    0,
                    terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET)
                )
                print(f"\r{msg}{' ' * padding}", end='', flush=True)

                # Run scraping; returns latest URL and whether new chapter was found
                series['latest'], found = scraper.scrape_chapters()
                if found:
                    new_chapter_found = True
            except HTTPError as e:
                # Handle HTTP 429 rate-limiting gracefully
                if e.response.status_code == 429:
                    print(
                        f"Skipping series due to rate limiting (HTTP 429): {series['name']}"
                    )
                    continue
                else:
                    raise
            except Exception as e:
                # Catch-all for unexpected errors per series
                print(f"An unexpected error occurred for '{series.get('name', 'Unnamed')}': {e}")
                continue

        # If no new chapters across all series, print a completion message
        if not new_chapter_found:
            msg = f"{GREEN}Scraping Complete - No New Chapters!{RESET}"
            padding = max(0, terminal_width - len(msg) + len(GREEN) + len(RESET))
            print(f"\r{msg}{' ' * padding}", end='', flush=True)
        print()  # Move to next line

        # Phase 2: Process TTS and audio merging
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            tmp = 'tmp'
            out = config['config']['output_dir']

            # Ensure working directories exist
            os.makedirs(tmp, exist_ok=True)
            os.makedirs(out, exist_ok=True)

            skipped = 0
            for idx, series in enumerate(config['series']):
                if not series.get('enabled', True):
                    skipped += 1
                    continue

                # Status message for audio generation
                msg = (
                    f"{GREEN}[{idx+1-skipped}/{total}] "
                    f"Generating {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                )
                padding = max(
                    0,
                    terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET)
                )
                print(f"\r{msg}{' ' * padding}", end='', flush=True)

                # Run the audio pipeline for this series
                input_dir = os.path.join(config['config']['output_dir'], series.get('name'), raws_subdir)
                process_series(input_dir, series, out, tmp, args.speed)
        print()

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print(f"\n{YELLOW}Scraping interrupted. "
              f"Updating the latest chapter info...{RESET}")
    finally:
        # Always save config updates (e.g., new 'latest' URLs)
        save_config(config_file, config)
import argparse
import warnings
import os
import shutil
import concurrent.futures
from urllib.parse import urlparse

from .config import load_config, save_config
from .scrapers.royalroad import RoyalRoadScraper
from .scrapers.scribblehub import ScribbleHubScraper
from .processors.processing import process_series
from .utils.colors import GREEN, PURPLE, YELLOW, RESET
from requests.exceptions import HTTPError

# Mapping domain substrings to scraper classes
SCRAPER_MAP = {
    "royalroad.com": RoyalRoadScraper,
    "scribblehub.com": ScribbleHubScraper,
}


def detect_source_from_url(url):
    """
    Choose the correct scraper based on URL domain.
    Returns the scraper class or None if no match.
    """
    domain = urlparse(url).netloc.lower()
    for key, cls in SCRAPER_MAP.items():
        if key in domain:
            return cls
    return None


def main():
    """
    CLI entry point:
      - Parse arguments
      - Load config
      - Phase 1: Parallel scraping of series
      - Phase 2: Sequential TTS/audio processing
      - Save updated config
    """
    parser = argparse.ArgumentParser(
        description='Convert text to speech and adjust playback speed for all series.'
    )
    parser.add_argument('--speed', type=float, default=1.0,
                        help="Playback speed multiplier (e.g., 1.2 for 20% faster).")
    parser.add_argument('--dev', action='store_true',
                        help='Use development config (config_dev.yml).')
    args = parser.parse_args()

    # Load config
    config_file = 'config_dev.yml' if args.dev else 'config.yml'
    config = load_config(config_file)
    raws_subdir = 'raws'

    # Prepare progress printing
    terminal_width = shutil.get_terminal_size(fallback=(80, 20)).columns
    total = sum(1 for s in config['series'] if s.get('enabled', True))
    if total == 0:
        print(f"{YELLOW}No enabled series found.{RESET}")
        return

    skipped_count = sum(1 for s in config['series'] if not s.get('enabled', True))
    new_chapters = False

    try:
        # --- Phase 1: Parallel scraping ---
        def scrape_worker(idx, series, skip_offset):
            name = series.get('name', 'Unnamed')
            url = series.get('url', '')
            scraper_cls = detect_source_from_url(url)
            if not scraper_cls:
                print(f"{YELLOW}No scraper for {url}, skipping {name}.{RESET}")
                return idx, None, False

            out_dir = os.path.join(config['config']['output_dir'], name, raws_subdir)
            scraper = scraper_cls(series, out_dir)

            # Print status in place
            msg = f"{GREEN}[{idx+1 - skip_offset}/{total}] Scraping {PURPLE}{name}{RESET}"
            pad = max(0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET))
            print(f"\r{msg}{' '*pad}", end='', flush=True)

            try:
                latest_url, found = scraper.scrape_chapters()
            except HTTPError as e:
                if e.response.status_code == 429:
                    print(f"\n{YELLOW}Rate limited on {name}, skipping...{RESET}")
                    return idx, None, False
                raise
            except Exception as e:
                print(f"\n{YELLOW}Error scraping {name}: {e}{RESET}")
                return idx, None, False

            return idx, latest_url, found

        # Submit tasks
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, total)) as executor:
            for idx, series in enumerate(config['series']):
                if not series.get('enabled', True):
                    continue
                futures.append(executor.submit(scrape_worker, idx, series, skipped_count))

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                idx, latest_url, found = future.result()
                if latest_url:
                    config['series'][idx]['latest'] = latest_url
                if found:
                    new_chapters = True

        # Print completion or new-chapter status
        if not new_chapters:
            msg = f"{GREEN}Scraping Complete - No New Chapters!{RESET}"
            pad = max(0, terminal_width - len(msg) + len(GREEN) + len(RESET))
            print(f"\r{msg}{' '*pad}", end='', flush=True)
        print()

        # --- Phase 2: Audio processing ---
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=FutureWarning)
            tmp = 'tmp'
            out = config['config']['output_dir']
            os.makedirs(tmp, exist_ok=True)
            os.makedirs(out, exist_ok=True)

            skipped_count = sum(1 for s in config['series'] if not s.get('enabled', True))
            for idx, series in enumerate(config['series']):
                if not series.get('enabled', True):
                    continue

                name = series.get('name', 'Unnamed')
                msg = f"{GREEN}[{idx+1 - skipped_count}/{total}] Generating {PURPLE}{name}{RESET}"
                pad = max(0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET))
                print(f"\r{msg}{' '*pad}", end='', flush=True)

                input_dir = os.path.join(out, name, raws_subdir)
                process_series(input_dir, series, out, tmp, args.speed)
        print()

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print(f"\n{YELLOW}Scraping interrupted. Updating the latest chapter info...{RESET}")

    finally:
        # Always save config updates (e.g., new 'latest' URLs)
        save_config(config_file, config)


if __name__ == '__main__':
    main()

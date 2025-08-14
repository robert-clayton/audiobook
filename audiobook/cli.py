import argparse
import warnings
import os
import shutil
import sys
from urllib.parse import urlparse
from .config import load_config, save_config
from .scrapers.royalroad import RoyalRoadScraper
from .scrapers.scribblehub import ScribbleHubScraper
from .processors.processing import process_series
from .utils.colors import GREEN, PURPLE, YELLOW, RED, RESET
from .utils.logger import setup_logger
from requests.exceptions import HTTPError

# Setup logging
try:
    logger = setup_logger("audiobook-cli", log_file=None)
except:
    logger = None

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
        description="Convert text to speech and adjust playback speed for all series in the inputs folder"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (e.g., 1.2 for 20% faster)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use the development config file (config_dev.yml)",
    )
    parser.add_argument(
        "--series",
        type=str,
        help="Process only a specific series by name",
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Skip the scraping phase and only process existing files",
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Skip the TTS processing phase and only scrape new chapters",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually doing it",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed logging",
    )
    parser.add_argument(
        "--max-chapters",
        type=int,
        help="Maximum number of chapters to process per series (useful for testing)",
    )
    args = parser.parse_args()

    # Set log level based on verbose flag
    if args.verbose and logger:
        logger.setLevel("DEBUG")

    # Choose config file based on dev flag, then load it
    config_file = "config_dev.yml" if args.dev else "config.yml"
    try:
        config = load_config(config_file)
    except FileNotFoundError:
        print(f"{RED}Configuration file '{config_file}' not found.{RESET}")
        print(f"Please create a {config_file} file or use --dev for development mode.")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Error loading configuration: {e}{RESET}")
        sys.exit(1)

    raws_subdir = "raws"

    # Determine terminal width for clean in-place printing
    terminal_width = shutil.get_terminal_size(fallback=(80, 20)).columns
    new_chapter_found = False
    
    try:
        # Filter series based on --series argument
        all_series = config["series"]
        if args.series:
            series_to_scrape = [s for s in all_series if s.get("name") == args.series]
            if not series_to_scrape:
                print(f"{RED}Series '{args.series}' not found in configuration.{RESET}")
                print(f"Available series: {[s.get('name') for s in all_series]}")
                sys.exit(1)
        else:
            series_to_scrape = [s for s in all_series if s.get("enabled", True)]
        
        total = len(series_to_scrape)
        if total == 0:
            print(f"{YELLOW}No enabled series found in the configuration.{RESET}")
            return

        if args.dry_run:
            print(f"{GREEN}DRY RUN - Would process {total} series:{RESET}")
            for series in series_to_scrape:
                print(f"  - {series.get('name')} ({series.get('url', 'No URL')})")
            return

        if logger:
            logger.info(f"Starting processing for {total} series")
        
        # Phase 1: Scrape new chapters (unless skipped)
        if not args.skip_scraping:
            print(f"{GREEN}Phase 1: Scraping new chapters...{RESET}")
            skipped = 0
            for idx, series in enumerate(series_to_scrape):
                if not series.get("enabled", True):
                    skipped += 1
                    continue

                url = series.get("url", "")
                scraper_cls = detect_source_from_url(url)

                if not scraper_cls:
                    print(
                        f"{YELLOW}Could not determine scraper for URL: {url}. "
                        f"Skipping '{series.get('name', 'Unnamed')}'...{RESET}"
                    )
                    continue

                # Initialize scraper with series config and output directory
                output_dir = os.path.join(
                    config["config"]["output_dir"], series.get("name"), raws_subdir
                )
                scraper = scraper_cls(series, output_dir)
                try:
                    # Prepare status message and pad to clear line
                    msg = (
                        f"{GREEN}[{idx+1}/{total}] "
                        f"Scraping {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                    )
                    padding = max(
                        0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET)
                    )
                    print(f"\r{msg}{' ' * padding}", end="", flush=True)

                    # Run scraping; returns latest URL and whether new chapter was found
                    series["latest"], found = scraper.scrape_chapters()
                    if found:
                        new_chapter_found = True
                        if logger:
                            logger.info(f"New chapters found for {series.get('name')}")
                except HTTPError as e:
                    # Handle HTTP 429 rate-limiting gracefully
                    if e.response.status_code == 429:
                        print(
                            f"\n{YELLOW}Skipping series due to rate limiting (HTTP 429): {series['name']}{RESET}"
                        )
                        continue
                    else:
                        if logger:
                            logger.error(f"HTTP error for {series.get('name')}: {e}")
                        print(f"\n{RED}HTTP error for '{series.get('name', 'Unnamed')}': {e}{RESET}")
                        continue
                except Exception as e:
                    # Catch-all for unexpected errors per series
                    if logger:
                        logger.error(f"Unexpected error for {series.get('name')}: {e}")
                    print(
                        f"\n{RED}An unexpected error occurred for '{series.get('name', 'Unnamed')}': {e}{RESET}"
                    )
                    continue

            # If no new chapters across all series, print a completion message
            if not new_chapter_found:
                msg = f"{GREEN}Scraping Complete - No New Chapters!{RESET}"
                padding = max(0, terminal_width - len(msg) + len(GREEN) + len(RESET))
                print(f"\r{msg}{' ' * padding}", end="", flush=True)
            print()  # Move to next line
        else:
            print(f"{YELLOW}Skipping scraping phase as requested.{RESET}")

        # Phase 2: Process TTS and audio merging (unless skipped)
        if not args.skip_processing:
            print(f"{GREEN}Phase 2: Processing TTS and audio...{RESET}")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=FutureWarning)
                tmp = "tmp"
                out = config["config"]["output_dir"]

                # Ensure working directories exist
                os.makedirs(tmp, exist_ok=True)
                os.makedirs(out, exist_ok=True)

                series_to_process = series_to_scrape  # Use same filtered list
                for idx, series in enumerate(series_to_process):
                    # Status message for audio generation
                    msg = (
                        f"{GREEN}[{idx+1}/{total}] "
                        f"Generating {PURPLE}{series.get('name', 'Unnamed')}{RESET}"
                    )
                    padding = max(
                        0, terminal_width - len(msg) + len(GREEN) + len(PURPLE) + len(RESET)
                    )
                    print(f"\r{msg}{' ' * padding}", end="", flush=True)

                    # Run the audio pipeline for this series
                    input_dir = os.path.join(
                        config["config"]["output_dir"], series.get("name"), raws_subdir
                    )
                    try:
                        process_series(input_dir, series, out, tmp, args.speed, max_chapters=args.max_chapters)
                        if logger:
                            logger.info(f"Successfully processed {series.get('name')}")
                    except Exception as e:
                        if logger:
                            logger.error(f"Error processing {series.get('name')}: {e}")
                        print(f"\n{RED}Error processing '{series.get('name', 'Unnamed')}': {e}{RESET}")
                        continue
            print()
        else:
            print(f"{YELLOW}Skipping processing phase as requested.{RESET}")

        print(f"{GREEN}Processing complete!{RESET}")

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print(
            f"\n{YELLOW}Processing interrupted. "
            f"Updating the latest chapter info...{RESET}"
        )
        if logger:
            logger.info("Processing interrupted by user")
    except Exception as e:
        if logger:
            logger.error(f"Unexpected error: {e}")
        print(f"\n{RED}An unexpected error occurred: {e}{RESET}")
        sys.exit(1)
    finally:
        # Always save config updates (e.g., new 'latest' URLs)
        try:
            save_config(config_file, config)
            if logger:
                logger.info("Configuration saved successfully")
        except Exception as e:
            if logger:
                logger.error(f"Error saving configuration: {e}")
            print(f"{RED}Warning: Could not save configuration updates: {e}{RESET}")


if __name__ == "__main__":
    main()

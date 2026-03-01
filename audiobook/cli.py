"""CLI entry point for the audiobook pipeline (scrape chapters, then generate audio)."""

import argparse
import os
from .config import load_config, save_config
from .state import ChapterDB
from .pipeline import run_scrape_phase, run_audio_phase, print_summary
from .utils.colors import YELLOW, RESET


def main():
    """CLI entry point: parse args, scrape new chapters, then run the TTS audio pipeline."""
    parser = argparse.ArgumentParser(
        description='Scrape web novel chapters and convert to audiobooks using TTS.'
    )
    parser.add_argument(
        '--dev', action='store_true',
        help='Use the development config file (config_dev.yml).'
    )
    parser.add_argument(
        '--cli', action='store_true',
        help='Run in headless CLI mode (no GUI).'
    )
    args = parser.parse_args()

    if not args.cli:
        from .web.app import launch
        launch(dev_mode=args.dev)
        return

    config_file = 'config_dev.yml' if args.dev else 'config.yml'
    config = load_config(config_file)

    out_dir = config['config']['output_dir']
    db_path = os.path.join(out_dir, 'audiobook.db')
    db = ChapterDB(db_path)

    try:
        series_to_scrape = [s for s in config['series'] if s.get('enabled', True)]
        if len(series_to_scrape) == 0:
            print(f"{YELLOW}No enabled series found in the configuration.{RESET}")
            return

        run_scrape_phase(config, db)
        run_audio_phase(config, db, dev_mode=args.dev)
        print_summary(config, db)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Scraping interrupted. "
              f"Updating the latest chapter info...{RESET}")
    finally:
        save_config(config_file, config)
        db.close()

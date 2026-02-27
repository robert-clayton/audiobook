"""Orchestrates the TTS pipeline for a single series: validate, synthesize, speed-adjust, and convert."""

import os
import traceback
from .tts_processor import TTSProcessor
from ..utils.audio import change_playback_speed, convert_to_mp3
from ..utils.colors import PURPLE, RED, RESET


def process_series(input_dir, series_cfg, output_base, tmp_dir, speed):
    """Process all chapter .txt files in a series directory through the TTS pipeline.

    Args:
        input_dir: Directory containing raw chapter .txt files.
        series_cfg: Series configuration dict from config.yml.
        output_base: Base output directory for generated audio.
        tmp_dir: Temporary directory for intermediate WAV chunks.
        speed: Playback speed multiplier applied to final audio.
    """
    series_out = os.path.join(output_base, series_cfg.get('name', ''))
    os.makedirs(series_out, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    for root, _, files in os.walk(input_dir):
        for fname in files:
            if not fname.endswith('.txt'):
                continue
            path = os.path.join(root, fname)
            processor = TTSProcessor(path, series_cfg, output_dir=series_out, tmp_dir=tmp_dir)
            if processor.check_already_exists():
                continue
            pretty = os.path.splitext(fname)[0]
            # remove everything before first underscore
            pretty = pretty.split('_', 1)[-1] if '_' in pretty else pretty
            print(f"\n\t{PURPLE}{pretty}{RESET}")
            try:
                processor.validate_file(series_cfg.get('replacements', {}))
                processor.convert_text_to_speech()
                change_playback_speed(processor.output_path, speed)
                convert_to_mp3(processor.output_path, processor.output_path_mp3)
            except Exception as e:
                print(f"\t{RED}Error on {path}: {e}{RESET}")
                traceback.print_exc()
            finally:
                processor.clean_up()




import os
import traceback
import concurrent.futures
from pathlib import Path
from tqdm import tqdm
from .tts_processor import TTSProcessor
from ..utils.audio import change_playback_speed, convert_to_mp3
from ..utils.colors import PURPLE, RESET, GREEN, YELLOW
from ..utils.logger import get_logger

logger = get_logger(__name__)


def process_series(input_dir, series_cfg, output_base, tmp_dir, speed, max_chapters=None, max_workers=2):
    """
    Process a series with parallel TTS generation.
    
    Args:
        input_dir: Directory containing text files
        series_cfg: Series configuration
        output_base: Base output directory
        tmp_dir: Temporary directory
        speed: Playback speed multiplier
        max_chapters: Maximum chapters to process (for testing)
        max_workers: Maximum parallel workers for TTS
    """
    series_out = os.path.join(output_base, series_cfg.get("name", ""))
    os.makedirs(series_out, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    # Collect all text files to process
    text_files = []
    for root, _, files in os.walk(input_dir):
        for fname in files:
            if fname.endswith(".txt"):
                text_files.append(os.path.join(root, fname))
    
    # Sort files for consistent processing order
    text_files.sort()
    
    # Limit files if max_chapters specified
    if max_chapters:
        text_files = text_files[:max_chapters]
        logger.info(f"Limited to {max_chapters} chapters for testing")

    if not text_files:
        logger.info(f"No text files found in {input_dir}")
        return

    logger.info(f"Processing {len(text_files)} chapters for {series_cfg.get('name')}")

    # Process files with progress bar
    with tqdm(total=len(text_files), desc=f"Processing {series_cfg.get('name')}", unit="chapter") as pbar:
        if max_workers > 1 and len(text_files) > 1:
            # Parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for file_path in text_files:
                    future = executor.submit(
                        process_single_file, 
                        file_path, 
                        series_cfg, 
                        series_out, 
                        tmp_dir, 
                        speed
                    )
                    futures.append(future)
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            pbar.set_postfix({"status": "success"})
                        else:
                            pbar.set_postfix({"status": "skipped"})
                    except Exception as e:
                        logger.error(f"Error in parallel processing: {e}")
                        pbar.set_postfix({"status": "error"})
                    finally:
                        pbar.update(1)
        else:
            # Sequential processing
            for file_path in text_files:
                try:
                    result = process_single_file(file_path, series_cfg, series_out, tmp_dir, speed)
                    if result:
                        pbar.set_postfix({"status": "success"})
                    else:
                        pbar.set_postfix({"status": "skipped"})
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    pbar.set_postfix({"status": "error"})
                finally:
                    pbar.update(1)


def process_single_file(file_path, series_cfg, output_dir, tmp_dir, speed):
    """
    Process a single text file.
    
    Returns:
        bool: True if file was processed, False if skipped
    """
    try:
        processor = TTSProcessor(
            file_path, series_cfg, output_dir=output_dir, tmp_dir=tmp_dir
        )
        
        if processor.check_already_exists():
            return False  # Skipped
        
        pretty = os.path.splitext(os.path.basename(file_path))[0]
        # remove everything before first underscore
        pretty = pretty.split("_", 1)[-1] if "_" in pretty else pretty
        
        logger.info(f"Processing chapter: {pretty}")
        
        processor.validate_file(series_cfg.get("replacements", {}))
        processor.convert_text_to_speech()
        change_playback_speed(processor.output_path, speed)
        convert_to_mp3(processor.output_path, processor.output_path_mp3)
        
        return True  # Successfully processed
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        traceback.print_exc()
        return False
    finally:
        try:
            processor.clean_up()
        except:
            pass  # Ignore cleanup errors

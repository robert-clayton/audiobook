import re
import os
import subprocess
import argparse
import yaml
import warnings
import traceback
from requests.exceptions import HTTPError
from validate_file import validate
from royalroad import RoyalRoadScraper
from TTS.api import TTS
import nltk
from nltk.tokenize import sent_tokenize
from tqdm import tqdm


GREEN_TEXT  = "\033[92m"    # ANSI escape code for green
YELLOW_TEXT = "\033[93m"    # ANSI escape code for yellow
PURPLE_TEXT = "\033[95m"    # ANSI escape code for purple
RED_TEXT    = "\033[91m"    # ANSI escape code for red
RESET_COLOR = "\033[0m"     # Reset color

class TTSInstance:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TTSInstance, cls).__new__(cls)
            cls._instance.initialize(*args, **kwargs)
        return cls._instance

    def initialize(self, model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True):
        self.model = TTS(model_name=model_name, progress_bar=progress_bar).to("cuda")
    
    def tts_to_file(self, *args, **kwargs):
        return self.model.tts_to_file(*args, **kwargs)
        

class TTSProcessor:
    DEFAULT_NARRATOR = 'onyx'

    def __init__(self, file_name, config, output_dir, tmp_dir, max_chunk_size=250):
        self.file_name = file_name
        self.narrator = config.get('narrator', TTSProcessor.DEFAULT_NARRATOR)
        self.output_path = None
        self.cleaned_file_name = None
        self.tts = TTSInstance()
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir
        self.max_chunk_size = max_chunk_size
        self.speakers = self._load_speakers()
        self.character_speaker_mappings = config.get('mappings', {})
        self.system = config.get('system', {})

        self.base_output_file = f'{os.path.splitext(os.path.basename(self.file_name))[0]}'
        self.output_path = os.path.join(self.output_dir, f'{self.base_output_file}.wav')

    def _load_speakers(self):
        if not os.path.exists('speakers'):
            raise FileNotFoundError(f"Directory {self.speakers} does not exist.")

        speaker_files = [f for f in os.listdir('speakers') if f.endswith('.wav')]
        speaker_names = [os.path.splitext(f)[0] for f in speaker_files]
        return speaker_names

    def validate_file(self, series_specific_replacements):
        if not os.path.isfile(self.file_name):
            print(f"{RED_TEXT}File '{self.file_name}' does not exist.{RESET_COLOR}")
            raise FileNotFoundError(self.file_name)
        self.cleaned_file_name = validate(self.file_name, series_specific_replacements)

    def check_already_exists(self):
        return os.path.isfile(self.output_path)

    def convert_text_to_speech(self):
        temp_output_files = []

        if self.check_already_exists():
            return self.output_path

        # Read the text and split it into chunks
        with open(self.cleaned_file_name, "r", encoding="utf-8") as file:
            text = file.read()

        # Process text for each speaker
        parts = re.split(r'(\<\<SPEAKER=[^\>]+\>\>.*?\<</SPEAKER\>\>)', text, flags=re.DOTALL)
        parts = [part for part in parts if part.strip()]

        progress = tqdm(total=len(text), desc=f"{GREEN_TEXT}Generating Audio{RESET_COLOR}", unit="char")
        for idx, part in enumerate(parts):
            # Process speaker tags
            match = re.search(r'\<\<SPEAKER=([^\>]+)\>\>(.*?)\<</SPEAKER\>\>', part, flags=re.DOTALL)
            if match:
                speaker_name = self.narrator if match.group(1) == 'default' else match.group(1).lower()
                speaker_text = match.group(2)
            else:
                speaker_name = self.narrator
                speaker_text = part

            chunks = self._split_text(speaker_text)

            if speaker_name == 'system':
                is_system = True
                speaker_name = self.system.get('voice', TTSProcessor.DEFAULT_NARRATOR)
            else:
                is_system = False
            
            # Find speaker file for given character
            self.ensure_speaker_for_character(speaker_name)
            if speaker_name not in self.speakers:
                speaker_name = self.character_speaker_mappings[speaker_name]
            speaker_file = os.path.join('speakers', f'{speaker_name}.wav')

            for iidx, chunk in enumerate(chunks):
                # Update progress with the length of the current chunk
                progress.update(len(chunk))

                # Setup path vars
                speaker_output_file = f'{self.base_output_file}_part{idx}_{speaker_name}_chunk{iidx}.wav'
                speaker_output_path = os.path.join(self.tmp_dir, speaker_output_file)

                # Begin TTS if not already completed previously
                if not os.path.isfile(speaker_output_path):
                    # Remove <> from chunk because this TTS errors out with it
                    chunk = chunk.strip('<').strip('>')
                    # Perform TTS
                    self.tts.tts_to_file(text=chunk, speaker_wav=speaker_file, file_path=speaker_output_path, language="en")
                    # Apply modulation if SYSTEM part
                    if is_system:
                        speaker_output_path = self._modulate_system(speaker_output_path)

                temp_output_files.append(speaker_output_path)
        progress.close()

        # Merge the audio files if necessary
        if len(temp_output_files) > 1:
            self._merge_audio_files(temp_output_files)
        else:
            os.rename(temp_output_files[0], self.output_path)
        print(f"\t{GREEN_TEXT}Saved!")

    def ensure_speaker_for_character(self, speaker_name):
        if speaker_name not in self.speakers:
            if speaker_name not in self.character_speaker_mappings:
                # Ask the user for the correct mapping
                new_mapping = input(f"\t{YELLOW_TEXT}Character '{PURPLE_TEXT}{speaker_name}{YELLOW_TEXT}' is not mapped. Please provide a speaker (without extension): {RESET_COLOR}")
                if new_mapping in self.speakers:
                    self.character_speaker_mappings[speaker_name] = new_mapping
        #             print(f"\t\t{GREEN_TEXT}Mapping '{PURPLE_TEXT}{speaker_name}{GREEN_TEXT}' to '{PURPLE_TEXT}{new_mapping}{GREEN_TEXT}'{RESET_COLOR}")
        #         else:
        #             print(f"\t\t{RED_TEXT}Speaker '{PURPLE_TEXT}{new_mapping}{RED_TEXT}' not found. Please ensure the file exists in the './speakers' directory.{RESET_COLOR}")
        #     else:
        #         print(f"\t{GREEN_TEXT}Speaker '{PURPLE_TEXT}{speaker_name}{GREEN_TEXT}' already has a mapping.{RESET_COLOR}")
        # else:
        #     print(f"\t{GREEN_TEXT}Speaker '{PURPLE_TEXT}{speaker_name}{GREEN_TEXT}' is available.{RESET_COLOR}")

    def _modulate_system(self, path):
        temp_file = os.path.join(self.tmp_dir, 'temp_to_rename.wav')
        if os.path.isfile(temp_file):
            os.remove(temp_file)
        cmd = [
            'ffmpeg', 
            '-i', path,
            '-filter_complex', 'flanger=delay=20:depth=5,chorus=0.5:0.9:50:0.7:0.5:2',
            temp_file
        ]
        try:
            # Run ffmpeg and suppress output
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"\t{RED_TEXT}Error applying system modulation: {e}{RESET_COLOR}")
        os.replace(temp_file, path)
        return path

    def _split_text(self, text):
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = []

        current_chunk_size = 0
        for sentence in sentences:
            # Split the sentence if it's larger than the max_chunk_size
            while len(sentence) > self.max_chunk_size:
                # Find the split point within the sentence
                split_point = self.max_chunk_size
                # Avoid splitting in the middle of a word
                if split_point > 0 and sentence[split_point] not in {' ', '.', '!', '?', ',', ';'}:
                    while split_point > 0 and sentence[split_point] not in {' ', '.', '!', '?', ',', ';'}:
                        split_point -= 1
                if split_point == 0:
                    split_point = self.max_chunk_size

                # Split the sentence and add to the current chunk
                chunk_part = sentence[:split_point]
                sentence = sentence[split_point:].lstrip()  # Remove leading spaces from the remaining part

                # Add the chunk to the list
                if current_chunk_size + len(chunk_part) > self.max_chunk_size:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_chunk_size = 0

                current_chunk.append(chunk_part)
                current_chunk_size += len(chunk_part)
            
            # Handle the remaining part of the sentence
            if current_chunk_size + len(sentence) > self.max_chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_chunk_size = 0

            current_chunk.append(sentence)
            current_chunk_size += len(sentence)

        # Add any remaining text as the last chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _merge_audio_files(self, file_paths):
        # Merge audio files using ffmpeg
        with open('file_list.txt', 'w') as file_list:
            for file_path in file_paths:
                # Escape single quotes for ffmpeg
                escaped_file_path = file_path.replace("'", "'\\''")
                file_list.write(f"file '{escaped_file_path}'\n")
        
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', "file_list.txt",
            '-c', 'copy',
            self.output_path
        ]
        try:
            # Run ffmpeg and suppress output
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"\t{GREEN_TEXT}Merged!{RESET_COLOR}")
        except subprocess.CalledProcessError as e:
            print(f"\t{RED_TEXT}Called Process Error while merging audio files: {e}{RESET_COLOR}")
            traceback.print_exc()
        except Exception as e:
            print(f"\t{RED_TEXT}UNKNOWN ERROR while merging audio files: {e}{RESET_COLOR}")
            traceback.print_exc()
        os.remove('file_list.txt')

    def adjust_playback_speed(self, playback_speed):
        if playback_speed == 1.0:
            return

        adjusted_output_file = self.output_path.replace('.wav', '_faster.wav')
        cmd = [
            'ffmpeg',
            '-i', self.output_path,
            '-filter:a', f'atempo={playback_speed}',
            '-vn', adjusted_output_file
        ]

        try:
            # Run ffmpeg and suppress output
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(self.output_path)
            os.rename(adjusted_output_file, self.output_path)
            print(f"\t{GREEN_TEXT}Playback speed adjusted to: {PURPLE_TEXT}{playback_speed}{GREEN_TEXT}!{RESET_COLOR}")
        except subprocess.CalledProcessError as e:
            print(f"\t{RED_TEXT}Called Process Error while adjusting playback speed: {e}{RESET_COLOR}")
            traceback.print_exc()

    def clean_up(self):
        if self.cleaned_file_name:
            os.remove(self.cleaned_file_name)

def process_series(output_dir, config, playback_speed):
    input_dir = os.path.join('inputs', config.get('name', 'Unidentified'))
    series_dir = os.path.join(output_dir, config.get('name', 'Unidentified'))
    tmp_dir = os.path.join('tmp')

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(series_dir, exist_ok=True)
    for root, _, files in os.walk(input_dir):
        for file in files:
            if not file.endswith('.txt'):
                continue
            file_path = os.path.join(root, file)
            processor = TTSProcessor(file_path, config, output_dir=series_dir, tmp_dir=tmp_dir)
            if processor.check_already_exists():
                continue
            pretty_name = os.path.splitext(os.path.basename(file))[0].split('_', 1)[1]
            print(f'{PURPLE_TEXT}{pretty_name}{RESET_COLOR}')
            try:
                processor.validate_file(config.get('replacements', {}))
                processor.convert_text_to_speech()
                processor.adjust_playback_speed(playback_speed)
            except Exception as e:
                print(f"{RED_TEXT}Error while processing '{file_path}': {e}{RESET_COLOR}")
                traceback.print_exc()
            finally:
                processor.clean_up()

def dev_test(filename, config):
    output_dir = os.path.join('outputs', 'test')
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs('tmp', exist_ok=True)
    processor = TTSProcessor(filename, config, output_dir=output_dir)
    try:
        processor.validate_file({})
        processor.convert_text_to_speech()
        # processor.adjust_playback_speed('1.0')
    except Exception as e:
        print(f"{RED_TEXT}Error while processing '{filename}': {e}{RESET_COLOR}")
    finally:
        processor.clean_up()

def load(path):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)

def save(path, config):
    with open(path, 'w') as config_file:
        yaml.safe_dump(config, config_file, default_flow_style=False)

def main():
    nltk.download('punkt_tab')

    # Get user args
    parser = argparse.ArgumentParser(description='Convert text to speech and adjust playback speed for all series in the inputs folder.')
    parser.add_argument('--speed', type=float, default=1.0, help="Playback speed adjustment (e.g., 1.2 for 20\\% \\faster).")
    parser.add_argument('--dev', type=str, default='', help='Set if testing a new dev feature.')
    args = parser.parse_args()

    # Load config file
    config = load('config.yml')

    ## DEV MODE ONLY ##
    if args.dev:
        series = config['series'][0]
        dev_test(args.dev, series)
        return

    try:
        # Scrape
        for series in config['series']:
            if not series.get('enabled', True):
                continue
            scraper = RoyalRoadScraper(series)
            try:
                series['latest'] = scraper.scrape_chapters()
            except HTTPError as e:
                if e.response.status_code == 429:
                    print(f"Skipping series due to rate limiting (HTTP 429): {series['name']}")
                    continue
                else:
                    raise  # Re-raise other HTTP errors if they occur
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                continue

        # TTS + Suppress warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            for series in config['series']:
                if not series.get('enabled', True):
                    continue
                process_series(config['config']['output_dir'], series, args.speed)
    except KeyboardInterrupt:
        print(f"{YELLOW_TEXT}Scraping interrupted. Updating the latest chapter info...{RESET_COLOR}")
    finally:
        save('config.yml', config)


if __name__ == "__main__":
    main()

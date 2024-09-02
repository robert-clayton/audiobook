import torch
from TTS.api import TTS
import os
from validate_file import find_and_replace_smart_quotes
import subprocess
import argparse

class TTSProcessor:
    def __init__(self, file_name, speaker, playback_speed, output_dir):
        self.file_name = file_name
        self.speaker = f'speakers/{speaker}.wav'
        self.playback_speed = playback_speed
        self.model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        self.output_path = None
        self.cleaned_file_name = None
        self.tts = TTS(model_name=self.model_name, progress_bar=True).to("cuda")
        self.output_dir = output_dir

    def validate_file(self):
        if not os.path.isfile(self.file_name):
            print(f"File '{self.file_name}' does not exist.")
            raise FileNotFoundError(self.file_name)

    def clean_file(self):
        self.cleaned_file_name = find_and_replace_smart_quotes(self.file_name)

    def convert_text_to_speech(self):
        speaker_filepath_addition = self.speaker.split('/')[-1].split('.')[0]
        output_file = f'{os.path.splitext(os.path.basename(self.file_name))[0]}-{speaker_filepath_addition}.wav'
        self.output_path = os.path.join(self.output_dir, output_file)
        self.tts.tts_to_file(text=self._read_text_file(self.cleaned_file_name), 
                             speaker_wav=self.speaker, 
                             file_path=self.output_path, 
                             language="en")
        print(f"Audio saved to {self.output_path}")

    def _read_text_file(self, file_name):
        with open(file_name, "r", encoding="utf-8") as file:
            return file.read()

    def adjust_playback_speed(self):
        if self.playback_speed == 1.0:
            print("Playback speed is 1.0x; no adjustment needed.")
            return

        adjusted_output_file = self.output_path.replace('.wav', '_faster.wav')
        command = [
            'ffmpeg',
            '-i', self.output_path,
            '-filter:a', f'atempo={self.playback_speed}',
            '-vn', adjusted_output_file
        ]
        subprocess.run(command, check=True)
        os.remove(self.output_path)
        os.rename(adjusted_output_file, self.output_path)
        print(f"Adjusted audio saved to {self.output_path}")

    def clean_up(self):
        if self.cleaned_file_name:
            os.remove(self.cleaned_file_name)
            print(f"Cleaned text file '{self.cleaned_file_name}' has been deleted.")

def process_series(series_name, speaker, playback_speed):
    input_dir = f'inputs/{series_name}'
    output_dir = f'outputs/{series_name}'

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                processor = TTSProcessor(file_name=file_path, speaker=speaker, playback_speed=playback_speed, output_dir=output_dir)
                try:
                    processor.validate_file()
                    processor.clean_file()
                    processor.convert_text_to_speech()
                    processor.adjust_playback_speed()
                except Exception as e:
                    print(f"An error occurred while processing '{file_path}': {e}")
                finally:
                    processor.clean_up()

def main():
    parser = argparse.ArgumentParser(description='Convert text to speech and adjust playback speed for all series in the inputs folder.')
    parser.add_argument('--speaker', type=str, default='onyx', help='The path to the speaker WAV file.')
    parser.add_argument('--speed', type=float, default=1.0, help="Playback speed adjustment (e.g., 1.2 for 20% faster).")

    args = parser.parse_args()

    # Iterate over each series in the inputs folder
    input_folder = 'inputs'
    series_list = [d for d in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, d))]

    for series in series_list:
        process_series(series, speaker=args.speaker, playback_speed=args.speed)

if __name__ == "__main__":
    main()

import os
import subprocess
import argparse
from TTS.api import TTS
from validate_file import validate
from nltk.tokenize import sent_tokenize
import nltk

class TTSProcessor:
    def __init__(self, file_name, speaker, playback_speed, output_dir, max_chunk_size=250):
        self.file_name = file_name
        self.speaker = f'speakers/{speaker}.wav'
        self.playback_speed = playback_speed
        self.model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        self.output_path = None
        self.cleaned_file_name = None
        self.tts = TTS(model_name=self.model_name, progress_bar=True).to("cuda")
        self.output_dir = output_dir
        self.max_chunk_size = max_chunk_size

    def validate_file(self):
        if not os.path.isfile(self.file_name):
            print(f"File '{self.file_name}' does not exist.")
            raise FileNotFoundError(self.file_name)
        self.cleaned_file_name = validate(self.file_name)

    def convert_text_to_speech(self):
        speaker_filepath_addition = self.speaker.split('/')[-1].split('.')[0]
        base_output_file = f'{os.path.splitext(os.path.basename(self.file_name))[0]}_{speaker_filepath_addition}'
        temp_output_files = []

        # check if already converted this file
        if os.isfile(os.path.join(self.output_dir, f'{base_name}.wav')):
            print(f"Audio file already exists: <{os.path.join(self.output_dir, f'{base_name}.wav')}>.")
            return

        # Read the text and split it into chunks
        text = self._read_text_file(self.cleaned_file_name)
        chunks = self._split_text(text)

        for idx, chunk in enumerate(chunks):
            chunk_output_file = f'{base_output_file}_part{idx + 1}.wav'
            chunk_output_path = os.path.join(self.output_dir, 'tmp', chunk_output_file)

            if os.isfile(chunk_output_path):
                print(f"Audio for chunk {idx + 1} already exists at: {chunk_output_file}")
            else:
                self.tts.tts_to_file(text=chunk, speaker_wav=self.speaker, file_path=chunk_output_path, language="en")

            temp_output_files.append(chunk_output_path)
            print(f"Audio saved for chunk {idx + 1}: {chunk_output_file}")

        # Merge the audio files if necessary
        if len(temp_output_files) > 1:
            self._merge_audio_files(temp_output_files, base_output_file)
        
        print(f"Audio saved to {base_output_file}.wav")

    def _read_text_file(self, file_name):
        with open(file_name, "r", encoding="utf-8") as file:
            return file.read()

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

    def _merge_audio_files(self, file_paths, base_name):
        # Merge audio files using ffmpeg
        with open('file_list.txt', 'w') as file_list:
            for file_path in file_paths:
                file_list.write(f"file '{file_path}'\n")

        merged_output_file = os.path.join(self.output_dir, f'{base_name}.wav')
        command = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', 'file_list.txt',
            '-c', 'copy',
            merged_output_file
        ]
        subprocess.run(command, check=True)
        os.remove('file_list.txt')
        print(f"Audio files merged into {merged_output_file}")

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
    os.makedirs(f'{output_dir}/tmp', exist_ok=True)

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                processor = TTSProcessor(file_name=file_path, speaker=speaker, playback_speed=playback_speed, output_dir=output_dir)
                try:
                    processor.validate_file()
                    processor.convert_text_to_speech()
                    processor.adjust_playback_speed()
                except Exception as e:
                    print(f"An error occurred while processing '{file_path}': {e}")
                finally:
                    processor.clean_up()

def main():
    nltk.download('punkt_tab')

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

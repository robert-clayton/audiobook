import torch
from TTS.api import TTS
import sys
import os
from validate_file import find_and_replace_smart_quotes
import subprocess
import argparse

# Function to adjust playback speed using ffmpeg
def adjust_playback_speed(input_file, speed=1.0):
    if speed == 1.0:
        print("Playback speed is 1.0x; no adjustment needed.")
        return input_file

    # Prepare the output file path for the adjusted audio
    output_file = input_file.replace('.wav', '_faster.wav')

    # Execute ffmpeg command to adjust playback speed
    command = [
        'ffmpeg',
        '-i', input_file,
        '-filter:a', f'atempo={speed}',
        '-vn', output_file
    ]
    subprocess.run(command, check=True)

    return output_file

# Setup argument parser
parser = argparse.ArgumentParser(description='Convert text to speech and adjust playback speed.')
parser.add_argument('input_file', type=str, help='The path to the text file to convert.')
parser.add_argument('--speaker', type=str, default='onyx', help='The path to the speaker WAV file.')
parser.add_argument('--speed', type=float, default=1.0, help="Playback speed adjustment (e.g., 1.2 for 20% faster).")

# Parse arguments
args = parser.parse_args()

# Choose a model that is closest to OpenAI's Onyx
model_name = "tts_models/multilingual/multi-dataset/xtts_v2"

# Initialize TTS with the selected model
tts = TTS(model_name=model_name, progress_bar=True).to("cuda")

# Validate the file exists
if not os.path.isfile(f'inputs/{args.input_file}'):
  print(f"File '{input_file}' does not exist.")
  sys.exit(1)

# Validate and clean the file before processing
cleaned_input_file = find_and_replace_smart_quotes(f'inputs/{args.input_file}')

# Load the cleaned text from the file
with open(cleaned_input_file, "r", encoding="utf-8") as file:
  text = file.read()

# Convert text to speech
output_file = f'{os.path.splitext(args.input_file)[0]}-{args.speaker}.wav'
output_path = f'outputs/{output_file}'

tts.tts_to_file(text=text, speaker_wav=f'speakers/{args.speaker}.wav', file_path=output_path, language="en")

print(f"Audio saved to {output_file}")

# Adjust playback speed if needed
adjusted_output_file = adjust_playback_speed(output_path, speed=args.speed)

if args.speed != 1.0:
  print(f"Adjusted audio saved to {adjusted_output_file}")
  os.remove(output_path)
  os.rename(adjusted_output_file, output_path)
  print(f"Original audio file '{output_file}' has been replaced with the adjusted version.")

# Delete the cleaned text file
os.remove(cleaned_input_file)
print(f"Cleaned text file '{cleaned_input_file}' has been deleted.")

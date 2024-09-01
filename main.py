import torch
from TTS.api import TTS
import sys
import os
from validate_file import find_and_replace_smart_quotes

# Choose a model that is closest to OpenAI's Onyx
# model_name = "tts_models/en/ljspeech/tacotron2-DDC"  # Example model, adjust if needed
model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
speaker = "speakers/jewel.wav"

# Initialize TTS with the selected model
tts = TTS(model_name=model_name, progress_bar=True).to("cuda")

# Check for filename passed as a command-line argument
if len(sys.argv) > 1:
  file_name = sys.argv[1]
else:
  # Ask the user to input the file name
  file_name = input("Please enter the text file name: ")

# Validate the file exists
if not os.path.isfile(file_name):
  print(f"File '{file_name}' does not exist.")
  sys.exit(1)

# Validate and clean the file before processing
cleaned_file_name = find_and_replace_smart_quotes(file_name)

# Load the cleaned text from the file
with open(cleaned_file_name, "r", encoding="utf-8") as file:
  text = file.read()

# Convert text to speech
speaker_filepath_addition = speaker.split('/')[-1].split('.')[0]
output_file = f'{os.path.splitext(file_name)[0]}-{speaker_filepath_addition}.wav'
output_path = f'outputs/{output_file}'
tts.tts_to_file(text=text, speaker_wav=speaker, file_path=output_path, language="en")

print(f"Audio saved to {output_file}")

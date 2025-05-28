import subprocess
import os
from .colors import RED, GREEN, RESET


def merge_audio(file_paths, output_path):
    """Merge multiple audio files into a single WAV file using ffmpeg."""
    
    merge_succeeded = False
    with open('file_list.txt', 'w') as file_list:
        for file_path in file_paths:
            # Escape single quotes for ffmpeg
            escaped_file_path = file_path.replace("'", "'\\''")
            file_list.write(f"file '{escaped_file_path}'\n")

    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', 'file_list.txt',
        '-c', 'copy',
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"\t{GREEN}Merged!{RESET}")
        merge_succeeded = True
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error merging audio: {e}{RESET}")
        raise
    finally:
        os.remove('file_list.txt')
        return merge_succeeded

def modulate_audio(path, tmp_dir):
    """Apply flanger + chorus modulation to a WAV file."""
    temp_file = os.path.join(tmp_dir, 'temp_to_rename.wav')
    if os.path.exists(temp_file):
        os.remove(temp_file)
    cmd = [
        'ffmpeg',
        '-i', path,
        '-filter_complex', 'flanger=delay=20:depth=5,chorus=0.5:0.9:50:0.7:0.5:2',
        temp_file
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(temp_file, path)
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error applying modulation: {e}{RESET}")
    return path


def change_playback_speed(input_path, speed):
    """Adjust playback speed of a WAV file in-place."""
    if speed == 1.0:
        return input_path

    output = input_path.replace('.wav', '_faster.wav')
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-filter:a', f'atempo={speed}',
        '-vn',
        output
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(input_path)
        os.rename(output, input_path)
        print(f"\t{GREEN}Playback speed adjusted to: {speed}!{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error adjusting speed: {e}{RESET}")
        raise
    return input_path


def convert_to_mp3(wav_path, mp3_path):
    """Convert a WAV file to MP3 and remove the original WAV."""
    cmd = [
        'ffmpeg',
        '-i', wav_path,
        '-codec:a', 'libmp3lame',
        '-qscale:a', '2',
        mp3_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(wav_path)
        print(f"\t{GREEN}Converted to MP3!{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error converting to MP3: {e}{RESET}")
        raise
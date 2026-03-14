"""FFmpeg wrappers for audio merging, modulation, speed adjustment, and MP3 conversion."""

import subprocess
import os
from .colors import RED, GREEN, RESET


def merge_audio(file_paths, output_path):
    """Merge multiple audio files into a single WAV file using ffmpeg.

    Args:
        file_paths: List of paths to WAV files to concatenate.
        output_path: Destination path for the merged WAV file.

    Returns:
        True if merge succeeded, False otherwise.
    """
    
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
        '-af', 'apad=pad_dur=0.05,aresample=24000',
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
    """Apply flanger + chorus modulation to a WAV file in-place.

    Args:
        path: Path to the WAV file to modulate.
        tmp_dir: Temporary directory for intermediate files.

    Returns:
        The original path (file is modified in-place).
    """
    temp_file = os.path.join(tmp_dir, 'temp_to_rename.wav')
    if os.path.exists(temp_file):
        os.remove(temp_file)
    cmd = [
        'ffmpeg',
        '-i', path,
        '-filter_complex', 'flanger=delay=20:depth=5,chorus=0.5:0.9:50:0.7:0.5:2,volume=1.5',
        temp_file
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(temp_file, path)
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error applying modulation: {e}{RESET}")
    return path


def change_playback_speed(input_path, speed):
    """Adjust playback speed of a WAV file in-place using ffmpeg atempo filter.

    Args:
        input_path: Path to the WAV file.
        speed: Tempo multiplier (1.0 = no change, 1.2 = 20% faster).

    Returns:
        The original path (file is modified in-place). No-op if speed is 1.0.
    """
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
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error adjusting speed: {e}{RESET}")
        raise
    return input_path


def adjust_volume(input_path, volume):
    """Adjust volume of a WAV file in-place using ffmpeg volume filter.

    Args:
        input_path: Path to the WAV file.
        volume: Volume multiplier (1.0 = no change, 1.3 = 30% louder).

    Returns:
        The original path (file is modified in-place). No-op if volume is 1.0.
    """
    if volume == 1.0:
        return input_path

    output = input_path.replace('.wav', '_vol.wav')
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-filter:a', f'volume={volume}',
        '-vn',
        output
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(input_path)
        os.rename(output, input_path)
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error adjusting volume: {e}{RESET}")
        raise
    return input_path


def convert_to_mp3(wav_path, mp3_path):
    """Convert a WAV file to MP3 using libmp3lame and remove the original WAV.

    Args:
        wav_path: Source WAV file path.
        mp3_path: Destination MP3 file path.
    """
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
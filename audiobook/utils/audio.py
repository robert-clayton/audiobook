"""FFmpeg wrappers for audio merging, modulation, speed adjustment, and MP3 conversion."""

import re
import subprocess
import os
import tempfile
from .colors import RED, GREEN, RESET


def merge_audio(file_paths, output_path, timeout=None):
    """Merge multiple audio files into a single WAV file using ffmpeg.

    Args:
        file_paths: List of paths to WAV files to concatenate.
        output_path: Destination path for the merged WAV file.
        timeout: Optional seconds before the ffmpeg call is killed (guards against
            a hung/stalled write). Raises subprocess.TimeoutExpired on expiry.

    Returns:
        True if merge succeeded, False otherwise.
    """

    merge_succeeded = False
    # Write the concat list to a unique file in the OS temp dir (not the CWD, which
    # may be a Search-indexed/AV-watched folder that briefly locks new files) with
    # absolute entry paths so ffmpeg resolves them regardless of the list location.
    fd, list_path = tempfile.mkstemp(prefix='ffconcat_', suffix='.txt')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file_list:
            for file_path in file_paths:
                # Escape single quotes for ffmpeg
                escaped_file_path = os.path.abspath(file_path).replace("'", "'\\''")
                file_list.write(f"file '{escaped_file_path}'\n")

        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_path,
            '-af', 'apad=pad_dur=0.05,aresample=24000',
            output_path
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout)
            print(f"\t{GREEN}Merged!{RESET}")
            merge_succeeded = True
        except subprocess.TimeoutExpired:
            print(f"\t{RED}Timed out merging audio after {timeout}s{RESET}")
            raise
        except subprocess.CalledProcessError as e:
            print(f"\t{RED}Error merging audio: {e}{RESET}")
            raise
    finally:
        try:
            os.remove(list_path)
        except OSError:
            pass  # best-effort: a transient lock on the temp list must not fail the merge
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


def get_audio_duration(path):
    """Return audio duration in seconds via ffprobe, or None on failure."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        path
    ]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def id3_date(value):
    """Normalise a stored chapter date to an ID3v2.4 (TDRC) timestamp at noon.

    Accepts '2026-08-26', '2022-03-13 11:57' and the dated-filename form
    '2022-03-13T1157.00001'. Returns None for anything unrecognisable.

    Only the calendar date is kept, pinned to 12:00. audiobookshelf reads the
    tag as a UTC instant and shows it in the viewer's timezone, so a bare date
    or a midnight post rendered as the previous day in the US. Noon lands on the
    same day for any viewer within +/-12h of UTC. The exact posting time stays in
    the DB; chapter order comes from the track tag, not this.
    """
    m = re.match(r'\s*(\d{4}-\d{2}-\d{2})', str(value or ''))
    return f"{m.group(1)}T12:00" if m else None


def convert_to_mp3(wav_path, mp3_path, timeout=None, metadata=None):
    """Convert a WAV file to MP3 using libmp3lame and remove the original WAV.

    Args:
        wav_path: Source WAV file path.
        mp3_path: Destination MP3 file path.
        timeout: Optional seconds before the ffmpeg call is killed (guards against
            a hung/stalled write). Raises subprocess.TimeoutExpired on expiry; the
            source WAV is left in place so the step can be retried.
        metadata: Optional {tag: value} written as ID3v2.4 tags (title, album,
            date, track, ...). Players such as audiobookshelf order and label
            episodes from these, independent of the filename.
    """
    cmd = [
        'ffmpeg',
        '-y',
        '-i', wav_path,
        '-codec:a', 'libmp3lame',
        '-qscale:a', '2',
        '-id3v2_version', '4',
    ]
    for key, value in (metadata or {}).items():
        if value not in (None, ''):
            cmd += ['-metadata', f'{key}={value}']
    cmd.append(mp3_path)
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=timeout)
        os.remove(wav_path)
        print(f"\t{GREEN}Converted to MP3!{RESET}")
    except subprocess.TimeoutExpired:
        print(f"\t{RED}Timed out converting to MP3 after {timeout}s{RESET}")
        raise
    except subprocess.CalledProcessError as e:
        print(f"\t{RED}Error converting to MP3: {e}{RESET}")
        raise
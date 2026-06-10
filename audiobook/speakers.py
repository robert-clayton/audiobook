"""Helpers for the speakers/ voice-profile directory."""

import os

SPEAKERS_DIR = 'speakers'


def list_speakers(speakers_dir=SPEAKERS_DIR):
    """Return sorted speaker names (wav files without extension)."""
    if not os.path.isdir(speakers_dir):
        return []
    return sorted(
        os.path.splitext(f)[0] for f in os.listdir(speakers_dir) if f.endswith('.wav')
    )


def speaker_wav_path(name, speakers_dir=SPEAKERS_DIR):
    return os.path.join(speakers_dir, f'{name}.wav')


def transcript_path(name, speakers_dir=SPEAKERS_DIR):
    return os.path.join(speakers_dir, f'{name}.txt')

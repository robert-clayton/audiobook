# CLAUDE.md

## Project Overview

Automated pipeline for scraping web novel chapters (RoyalRoad, ScribbleHub) and converting them to audiobooks using Qwen3 TTS Base with multi-speaker voice cloning and audio effects.

**Actively used in production** — changes must be careful and non-breaking.

## Tech Stack

- **Language:** Python 3.11 (strict: >=3.11, <3.12)
- **Dependency Manager:** uv
- **TTS Engine:** Qwen3 TTS Base (default, voice cloning, CUDA-accelerated); optional Coqui TTS (XTTS v2)
- **Audio Processing:** FFmpeg (external dependency, must be on PATH)
- **ML:** PyTorch 2.5.1 + CUDA 12.1, Transformers
- **Scraping:** BeautifulSoup4, requests, cloudscraper (CloudFlare bypass)
- **Text Processing:** NLTK (sentence tokenization)

## Commands

```bash
# Install dependencies
uv sync

# Run the pipeline (scrape + generate audio)
uv run audiobook [--speed 1.2] [--dev]

# --speed: playback speed multiplier (default 1.0)
# --dev:   use config_dev.yml instead of config.yml
#          Both loading AND saving use the same file, so --dev
#          keeps production config.yml untouched (latest URLs
#          persist back to config_dev.yml only).
```

### Coqui TTS Setup (separate venv)

Coqui TTS requires `transformers<4.41`, which conflicts with Qwen3 TTS (`transformers>=4.57`).
To use the Coqui engine, create a separate venv:

```bash
uv venv .venv-coqui --python 3.11
# Linux/macOS:
source .venv-coqui/bin/activate
# Windows:
.venv-coqui\Scripts\activate

uv pip install coqui-tts nltk bs4 cloudscraper python-dotenv
uv pip install --reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu121
uv pip install -e . --no-deps       # audiobook entry point only
# Set tts_engine: coqui in config.yml, then:
python -m audiobook
```

### Adding new speakers

To add a new speaker voice profile, extract a reference audio clip and generate a transcript.

**From an audiobook (.m4b) on the network share:**
```bash
# Extract a clip (e.g., 20s starting at 5:00) as 24kHz mono WAV
ffmpeg -ss 300 -t 20 -i "//10.0.0.2/media/audiobooks/path/to/book.m4b" -ar 24000 -ac 1 -y speakers/<name>.wav

# Generate transcript
whisper speakers/<name>.wav --model base --output_format txt --output_dir speakers/
```

**From a YouTube video/short:**
```bash
# Download audio
yt-dlp -x --audio-format wav -o speakers/<name>.wav "<youtube_url>"

# Trim to desired segment (e.g., seconds 0-6)
ffmpeg -ss 0 -t 6 -i speakers/<name>.wav -ar 24000 -ac 1 -y speakers/<name>_trimmed.wav
mv speakers/<name>_trimmed.wav speakers/<name>.wav

# (Optional) Isolate vocals if clip has background music/noise
uv run --with soundfile demucs --mp3 -n htdemucs --two-stems vocals speakers/<name>.wav
# Copy the vocals output back, then re-convert to 24kHz mono WAV

# Generate transcript
whisper speakers/<name>.wav --model base --output_format txt --output_dir speakers/
```

**Guidelines:**
- 10-60 seconds of clean speech is ideal; longer is not necessarily better
- 24kHz mono WAV format required (`-ar 24000 -ac 1`)
- Speaker name must match narrator/mapping values in config (without extension)
- The `.txt` transcript significantly improves voice cloning quality; without it, falls back to x-vector-only mode

## Architecture

```
audiobook/
├── __main__.py          # Entry point → cli.main()
├── cli.py               # Two-phase pipeline: scrape, then process audio
├── config.py            # YAML config loader/saver
├── scrapers/
│   ├── base.py          # Abstract BaseScraper, anti-scrape filters, char normalization
│   ├── royalroad.py     # RoyalRoad scraper with system message detection
│   └── scribblehub.py   # ScribbleHub scraper with CloudFlare bypass
├── processors/
│   ├── processing.py    # Orchestrates TTS pipeline per series
│   ├── tts_processor.py # Core TTS: chunking, speaker mapping, audio merging
│   ├── tts_instance.py  # Singleton Coqui TTS model (GPU, optional)
│   └── tts_qwen.py      # Singleton Qwen3 TTS model (GPU, default)
├── validators/
│   └── validate_file.py # Text cleaning: encoding fixes, acronyms, replacements
└── utils/
    ├── audio.py         # FFmpeg wrappers: merge, modulate, speed, mp3 convert
    └── colors.py        # ANSI terminal color codes
```

## Key Concepts

- **Two-phase pipeline:** Phase 1 scrapes all enabled series chapters. Phase 2 processes text → TTS → WAV → speed adjust → MP3.
- **Speaker tags:** `<<SPEAKER=name>>...<</SPEAKER>>` tags in text map characters to voice profiles in `speakers/` directory.
- **System voice:** Certain HTML elements (bold, italic, tables, etc.) get wrapped as "system" speaker with modulation effects (flanger + chorus).
- **Anti-scrape filtering:** `base.py` maintains 100+ hardcoded anti-piracy messages to strip from scraped content.
- **Config-driven:** `config.yml` defines series with URL, narrator voice, optional replacements, system message settings, and character-to-voice mappings.
- **Singleton TTS:** `TTSInstance` (Coqui) or `QwenTTSInstance` (Qwen3) loads the GPU model once, shared across all processing. Backend selected by `tts_engine` config field.
- **Speaker transcripts:** `speakers/*.txt` files contain reference audio transcripts for Qwen3 voice cloning quality. Missing `.txt` falls back to x-vector-only mode (lower quality).

## Data Flow

```
config.yml → scrape chapters → save .txt to {output_dir}/{series}/raws/
  → validate/clean text → split into chunks (750 chars Qwen / 250 chars Coqui) → TTS per chunk
  → modulate system voice → merge chunks → adjust speed → convert to MP3
```

## Configuration (config.yml)

Global `config:` section:
- `output_dir` — base output path
- `tts_engine` — `"qwen"` (default) or `"coqui"` to use Coqui TTS (XTTS v2)
- `pause` — per-narrator silence padding in seconds (e.g., `{travis_baldree: 0.1}`). Appended after each TTS chunk for the given speaker. Omit or set to `0`/`null` for no padding.

Each series entry supports:
- `name`, `url` (TOC), `latest` (auto-updated), `narrator` (speaker profile)
- `enabled` (default true), `replacements` (word substitutions)
- `system` — `{voice, modulate, speed, type: [bold, italic, bracket, angle, blockquote, table, center]}`
- `mappings` — character name → speaker profile

## Development Notes

- **No CI/CD, no linter config, no active tests.** The `tests/` dir exists but is empty.
- `dev/` directory contains experimental code (image gen, LLM tagging) and is gitignored.
- `config*.yml` files are gitignored — they contain user-specific series lists and network paths.
- `.env` holds `HUGGINGFACE_TOKEN` — never commit this.
- Output goes to a network share path configured in `config.yml`.

## Commit Convention

Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `enhance:`, `bugfix:`, `docs:`, `chore:`

## Important Warnings

- **config.yml is live state** — the `latest` field is auto-updated by the scraper to track progress. Do not reset or alter `latest` values without understanding the consequences.
- **Singleton TTS model** — changes to `tts_instance.py` affect all audio generation globally.
- **Anti-scrape list in base.py** — these strings must be exact matches of messages found on source sites. Do not reformat or deduplicate without verifying.
- **FFmpeg commands** — audio utils shell out to ffmpeg. Test changes with actual audio files.
- **Speaker files** — voice profiles in `speakers/` are WAV files used for voice cloning. Names must match narrator/mapping values in config (without extension). For Qwen3, companion `.txt` files with reference audio transcripts improve voice cloning quality.

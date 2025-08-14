# Audiobook Generator

This project is an automated pipeline for scraping, processing, and converting web novel chapters into high-quality audiobooks. It supports multiple sources and advanced audio processing, including effects and playback speed adjustment.

---

## ✨ Features

* 📖 Scrape chapters from **RoyalRoad** and **ScribbleHub**
* 🧠 Generate speech using **Coqui TTS**
* 🎵 Merge and apply audio effects with `ffmpeg`
* 🎧 Change playback speed
* 💪 Designed for batch processing and meta-progression tracking
* 🐇 Easily configurable via `config.yml`
* 🔍 **NEW**: Web interface for monitoring and control
* 📊 **NEW**: Progress tracking and resume capability
* ✅ **NEW**: Configuration validation
* 🧪 **NEW**: Comprehensive test suite
* 📝 **NEW**: Proper logging system

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/robert-clayton/audiobook.git
cd audiobook
```

### 2. Install Poetry (if not already installed)

#### Windows:

```bash
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

#### Linux/macOS:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Make sure Poetry is in your PATH. If not, use:

```bash
py -m poetry --version
```

### 3. Install dependencies

```bash
# Need build tools on windows: https://visualstudio.microsoft.com/visual-cpp-build-tools/
poetry install
```

---

## Usage

### Command Line Interface

```bash
# Process all series
poetry run audiobook

# Process a specific series
poetry run audiobook --series "Series Name"

# Use development configuration
poetry run audiobook --dev

# Skip scraping phase (only process existing files)
poetry run audiobook --skip-scraping

# Skip processing phase (only scrape new chapters)
poetry run audiobook --skip-processing

# Dry run - show what would be processed
poetry run audiobook --dry-run

# Enable verbose logging
poetry run audiobook --verbose

# Limit chapters for testing
poetry run audiobook --max-chapters 5

# Adjust playback speed
poetry run audiobook --speed 1.2

# Combine options
poetry run audiobook --series "My Series" --dev --verbose --max-chapters 3
```

### Web Interface

Start the web dashboard:

```bash
# Production mode (uses config.yml)
poetry run audiobook-web

# Development mode (uses config_dev.yml)
poetry run audiobook-web --dev

# Custom host and port
poetry run audiobook-web --host 127.0.0.1 --port 8080

# Enable debug mode
poetry run audiobook-web --debug
```

The web interface will be available at `http://localhost:5000` (or your specified host/port).

### Development Tools

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black audiobook/
poetry run isort audiobook/
```

Type checking:
```bash
poetry run mypy audiobook/
```

Linting:
```bash
poetry run flake8 audiobook/
```

### Performance Monitoring

Generate performance reports:
```bash
# The system automatically tracks performance metrics
# View them in the web interface or check the metrics/ directory
```

### Cache Management

The system includes intelligent caching:
- **Processing Cache**: Tracks processed files to avoid re-processing
- **TTS Model Cache**: Keeps TTS models in memory for faster processing
- **Audio Cache**: Caches generated audio for reuse

Clear caches if needed:
```bash
# This can be done through the web interface
# or by deleting the .cache/ and .audio_cache/ directories
```

---

## ⚙️ Configuration

Edit `config.yml` or `config_dev.yml`:

```yaml
config:
  output_dir: \\192.168.0.1\your\mapped\network\location\media
series:
  - latest: https://www.royalroad.com/fiction/36049/the-primal-hunter/chapter/2309548/chapter-1095-beauty-brain
    name: The Primal Hunter
    narrator: onyx
    url: https://www.royalroad.com/fiction/36049/the-primal-hunter
  - latest: https://www.royalroad.com/fiction/24709/defiance-of-the-fall/chapter/2307815/chapter-1329-past-lifes-dream
    enabled: false
    name: Defiance of the Fall
    narrator: onyx
    url: https://www.royalroad.com/fiction/24709/defiance-of-the-fall
  - latest: https://www.royalroad.com/fiction/76463/mage-tank/chapter/2306656/273-the-truth-revealed
    name: Mage Tank
    narrator: onyx
    replacements:
      DR: Damage Reduction
    system:
      speed: 1.1
      modulate: true
      type:
      - bold
      voice: fable
    url: https://www.royalroad.com/fiction/76463/mage-tank
```

Each series entry includes:

* `name`: Display name
* `url`: Table of Contents url
* `latest`: Latest chapter url
* `narrator`: What voice to use for TTS synthesis. Must match name (sans ext) of files in `speakers/` 
* `enabled`: Toggle scraping for this series (optional, default `True`)
* `replacements`: Optional strings to replace from the source material (optional)
* `system`: Identify certain divs as from a "system" to modulate the audio for (optional)
  * Currently supported types: `bold`, `italic`, `bracket`, `braces`, `table`
  * Modulate adds a "tech-y" filter to the voice
  * Speed will speed up and down the system voice

---

## 💡 Structure

``` bash
audiobook/
├── scrapers/         # RoyalRoad and ScribbleHub specific scrapers
├── processors/       # TTS, audio merging, playback speed adjustments
├── utils/            # Logging, color codes, audio helpers
└── __main__.py       # CLI entry point
speakers/             # User-provided source audio for voice cloning
config.yml            # User-editable config
```

---

## 🚨 Troubleshooting

### "Poetry not on PATH"

Use `py -m poetry` or add Poetry to your shell PATH manually.

### FFmpeg Errors

Ensure `ffmpeg` is installed and accessible via your system PATH. You can verify with:

```bash
ffmpeg -version
```

---

## 📙 License

MIT License. See `LICENSE` file for details.

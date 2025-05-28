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
poetry install
```

---

## ▶️ Usage

```bash
poetry run audiobook [--speed 1.2] [--dev]
```

### Options

* `--speed`: Playback speed multiplier (default: 1.0)
* `--dev`: Use the development config file (`config_dev.yml`)

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
  * Currently supports : `bold`, `italic`, `bracket`, `braces`, `table`

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

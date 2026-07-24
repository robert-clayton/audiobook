# CLAUDE.md

## Project Overview

Automated pipeline for converting web novel chapters into audiobooks using Qwen3 TTS Base with multi-speaker voice cloning and audio effects. Supports scraping from RoyalRoad and ScribbleHub, as well as locally-managed chapter files (e.g. translated novels).

Runs as a React SPA web dashboard served by FastAPI (default), a legacy NiceGUI dashboard (`--legacy`), or headless CLI. State is tracked in SQLite for chapter-level status, retry, and filesystem reconciliation.

**Actively used in production** — changes must be careful and non-breaking.

## Tech Stack

- **Language:** Python 3.11 (strict: >=3.11, <3.12)
- **Dependency Manager:** uv
- **TTS Engine:** Qwen3 TTS Base (default, voice cloning, CUDA-accelerated); optional Coqui TTS (XTTS v2)
- **Web GUI:** React 19 SPA (Vite, TypeScript, Tailwind 4, TanStack Query/Table; industrial terminal theme) served by FastAPI + uvicorn; legacy NiceGUI 2.x UI behind `--legacy`
- **Audio Processing:** FFmpeg (external dependency, must be on PATH)
- **ML:** PyTorch 2.5.1 + CUDA 12.1, Transformers >=4.57
- **Scraping:** BeautifulSoup4, requests, cloudscraper (CloudFlare bypass)
- **Text Processing:** NLTK (sentence tokenization)
- **State:** SQLite via ChapterDB (series + chapters tables)

## Commands

```bash
# Install dependencies
uv sync

# Launch web dashboard (default, http://localhost:8080 — SPA + REST API)
uv run audiobook [--dev] [--no-browser] [--port 8181]

# Launch the legacy NiceGUI dashboard (instant rollback path)
uv run audiobook --legacy [--dev]

# Run headless CLI pipeline (scrape + generate)
uv run audiobook --cli [--dev]

# --dev: use config_dev.yml instead of config.yml
#        Both loading AND saving use the same file, so --dev
#        keeps production config.yml untouched.
```

### Frontend build (after changing frontend/src/)

`frontend/dist/` is **committed** so `git pull && uv run audiobook` works
without Node. Rebuild and commit dist alongside any frontend change:

```bash
cd frontend && npm install && npm run build
```

Hot-reload dev loop: see `frontend/README.md` (Vite on :5173 proxying /api
to a `--port` side instance).

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
python -m audiobook --cli
```

### Adding New Speakers

Extract a reference audio clip and generate a transcript for voice cloning.

**From an audiobook (.m4b) on the network share:**
```bash
ffmpeg -ss 300 -t 20 -i "//10.0.0.2/media/audiobooks/path/to/book.m4b" -ar 24000 -ac 1 -y speakers/<name>.wav
whisper speakers/<name>.wav --model base --output_format txt --output_dir speakers/
```

**From a YouTube video/short:**
```bash
yt-dlp -x --audio-format wav -o speakers/<name>.wav "<youtube_url>"
ffmpeg -ss 0 -t 6 -i speakers/<name>.wav -ar 24000 -ac 1 -y speakers/<name>_trimmed.wav
mv speakers/<name>_trimmed.wav speakers/<name>.wav

# (Optional) Isolate vocals if clip has background music/noise
uv run --with soundfile demucs --mp3 -n htdemucs --two-stems vocals speakers/<name>.wav

whisper speakers/<name>.wav --model base --output_format txt --output_dir speakers/
```

**Guidelines:**
- 10-60 seconds of clean speech is ideal
- 24kHz mono WAV format required (`-ar 24000 -ac 1`)
- Speaker name must match narrator/mapping values in config (without extension)
- The `.txt` transcript significantly improves voice cloning quality; without it, falls back to x-vector-only mode

## Architecture

```
audiobook/
├── __main__.py          # Entry point -> cli.main()
├── cli.py               # Arg parsing, launches GUI or headless CLI
├── config.py            # YAML config loader/saver
├── events.py            # PipelineEvent/PipelineContext: structured events + cooperative cancellation
├── pipeline.py          # All pipeline phases: scrape, audio, single-series/chapter ops
├── speakers.py          # speakers/ directory helpers (list, wav/transcript paths)
├── state.py             # ChapterDB: SQLite state tracking (series + chapters)
├── scrapers/
│   ├── base.py          # Abstract BaseScraper, 100+ anti-scrape filters, ChapterUnavailableError
│   ├── royalroad.py     # RoyalRoad scraper with system message detection
│   └── scribblehub.py   # ScribbleHub scraper with CloudFlare bypass
├── processors/
│   ├── processing.py    # Orchestrates TTS pipeline per series/chapter
│   ├── tts_processor.py # Core TTS: chunking, speaker tags, garbled detection, audio merging
│   ├── tts_instance.py  # Singleton Coqui TTS model (GPU, optional)
│   └── tts_qwen.py      # Singleton Qwen3 TTS model (GPU, default)
├── validators/
│   └── validate_file.py # Text cleaning: clean_text() + validate() file wrapper
├── utils/
│   ├── audio.py         # FFmpeg wrappers: merge, modulate, speed, mp3 convert, duration probe
│   └── colors.py        # ANSI terminal color codes
├── server/              # FastAPI server: REST API + SPA static serving (default GUI)
│   ├── main.py          # serve(): PipelineRunner + uvicorn on :8080
│   ├── app.py           # App factory: routers, ValueError→400, SPA mount
│   ├── deps.py          # get_runner dependency, open_db ctx (503 on dead share)
│   ├── spa.py           # frontend/dist static mount w/ client-route fallback
│   ├── health.py        # check_health (shared with legacy UI via re-import)
│   ├── util.py          # natural_key sort helper
│   └── routers/         # system, jobs, series, chapters, speakers, config, media
└── web/
    ├── app.py           # LEGACY NiceGUI app (uv run audiobook --legacy)
    ├── dashboard.py     # Legacy dashboard page
    ├── series_page.py   # Legacy series detail page
    ├── failed_page.py   # Legacy failed-chapter triage page
    ├── speakers_page.py # Legacy speaker manager page
    ├── config_dialogs.py# Legacy config dialogs
    ├── jobs.py          # JobQueue: FIFO worker thread, dedupe, cancel, event ring buffer
    ├── runner.py        # PipelineRunner facade: job submission, derived state, config lock
    ├── queue_panel.py   # Legacy queue panel UI
    ├── health.py        # Re-export shim → server/health.py
    ├── gui_log.py       # Seq-numbered log ring buffer + logging bridge
    ├── shared.py        # Legacy UI helpers
    ├── theme.py         # Legacy dark industrial theme
    └── log_capture.py   # Thread-aware stdout/stderr capture feeding gui_log

frontend/                # React SPA (see frontend/README.md)
├── src/api/             # Typed client + one function per endpoint
├── src/components/      # Industrial ui kit, tables, queue panel, dialogs
├── src/hooks/           # 2s status poll, log store, job submit/notify
├── src/routes/          # Dashboard, Series, Failed, Speakers pages
└── dist/                # COMMITTED build output served by audiobook/server
```

Note: `web/{runner,jobs,gui_log,log_capture}.py` are the UI-agnostic core the
API wraps — NOT legacy. The NiceGUI page modules are kept only as the
`--legacy` rollback path until the SPA has proven out; a later cleanup removes
them and the nicegui dependency.

## Key Concepts

- **Two-phase pipeline:** Phase 1 scrapes new chapters (skips local series). Phase 2 syncs filesystem, then processes text -> TTS -> WAV -> speed adjust -> MP3.
- **Local series:** Set `url: local` in config for manually-managed chapter files (e.g. translations). No scraping occurs; drop `.txt` files into `{output_dir}/{name}/raws/` and the audio phase picks them up via `sync_filesystem`.
- **Speaker tags:** `<<SPEAKER=name>>...<</SPEAKER>>` tags in text map characters to voice profiles in `speakers/`.
- **System voice:** Certain HTML elements (bold, italic, tables, etc.) get wrapped as "system" speaker with modulation effects (flanger + chorus).
- **Anti-scrape filtering:** `base.py` maintains 100+ hardcoded anti-piracy messages to strip from scraped content, including embedded removal within larger text blocks.
- **Config-driven:** `config.yml` defines series with URL, narrator, replacements, system message settings, and character-to-voice mappings.
- **Singleton TTS:** `QwenTTSInstance` (default) or `TTSInstance` (Coqui) loads the GPU model once, shared across all processing. Unloaded after each pipeline run.
- **Speaker transcripts:** `speakers/*.txt` files contain reference audio transcripts for Qwen3 voice cloning quality. Missing `.txt` falls back to x-vector-only mode (lower quality).
- **Garbled audio detection:** Chunks exceeding 100s duration are likely TTS hallucinations. Retried up to 2 times, then the chapter is marked failed.
- **ChapterDB:** SQLite database at `{output_dir}/audiobook.db` tracks chapter status (pending -> processing -> done/failed), raw/output paths, source URLs, retry counts.

## Data Flow

```
config.yml -> scrape chapters (or manually place in raws/) -> save .txt to {output_dir}/{series}/raws/
  -> sync_filesystem (register new files, reconcile DB state)
  -> validate/clean text -> split into chunks (750 chars Qwen / 250 chars Coqui)
  -> TTS per chunk (batched, 5 at a time) -> modulate system voice -> adjust narrator volume
  -> merge chunks -> convert to MP3
  -> mark done in DB
```

## Web GUI

The default launch mode serves the React SPA + REST API at `http://localhost:8080`
(FastAPI/uvicorn, no NiceGUI). `--legacy` serves the old NiceGUI dashboard
instead. Pages: `/` (dashboard), `/series/{name}`, `/failed?series=`,
`/speakers` — same feature set in both UIs.

**API:** everything lives under `/api/*` (see `audiobook/server/routers/`).
The SPA polls `GET /api/status?log_since=N` every 2s — one bundle carrying
pipeline state, queue snapshot, and incremental log lines via the seq-cursor
ring buffer. Health polls at 10s. DB-touching endpoints are sync `def`
(threadpool) and return 503 when the SMB share is unreachable; interactive
flows (rescrape preview, filename fixes, resync, sync) return 409 while a job
runs. Audio streams from `/api/audio/{chapter_id}` and
`/api/speaker_audio/{name}` (identical paths in both UIs).

**Dashboard (`/`):**
- Series summary table (done/pending/failed counts per series)
- Pipeline controls: Run Full Pipeline, Scrape Only, Sync Filesystem
- Health strip, generation stats, live log terminal
- Pipeline state indicator (Idle/Scraping/Generating/Finished/Error)

**Series page (`/series/{name}`):**
- Chapter table with status (+ live % on the processing chapter), natural
  numeric title sort, published date, error tooltips
- Per-series actions: Scrape, Generate, Rescrape Series (diff review dialog),
  Fix Filenames, Resync, Edit Config
- Per-chapter actions: open (audio + raw text edit + cleaned preview),
  Regenerate, Rescrape (diff preview)

**Runner & job queue:** GUI operations are submitted as jobs to an in-memory FIFO
`JobQueue` (single worker thread). Key behaviors:
- Jobs queue instead of being rejected while one runs; identical jobs dedupe
- Cooperative cancellation: a cancelled chapter resets to pending; temp chunk WAVs are kept for resume
- Per-job config reload; at job end only changed `latest` cursors merge back into a fresh
  config load (lock shared with `runner.update_config`, so GUI config edits are always safe)
- TTS model unloads when the queue drains (not per job)
- Crash recovery (reset stale "processing" chapters on shutdown)
- Pipeline emits structured `PipelineEvent`s (chapter/chunk progress) consumed by the queue panel;
  CLI passes no context and is unaffected

## Configuration (config.yml)

```yaml
config:
  output_dir: //10.0.0.2/media/audiobooks/Generated
  tts_engine: qwen          # or "coqui"
  tts_batch_size: 5         # chunks per TTS generate call (VRAM-bound; default 5)
  tts_verbose: false        # per-phase timing lines ([t] gen/merge/mp3) in the log
  narrators:                 # per-narrator settings (pause, volume)
    default:
      pause: 0.3             # default silence padding for all narrators
    jareth:
      pause: 0.3
      volume: 1.3            # loudness correction (1.0 = no change)
    katie:
      pause: 0.2

series:
  # Web novel (scraped)
  - name: Series Name
    url: https://www.royalroad.com/fiction/12345/series-name
    narrator: travis_baldree
    latest: https://...       # auto-updated by scraper
    enabled: true             # default true
    replacements:
      Mana: mah-nah
    system:
      voice: onyx
      modulate: true
      speed: 1.0
      type: [bold, italic, bracket, angle, blockquote, table, center]
    mappings:
      Character A: speaker_one
      Character B: speaker_two

  # Local series (manually managed)
  - name: "That's It. Let's Turn Slaves into Adventurers"
    url: local
    narrator: some_speaker
```

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
- **Singleton TTS model** — changes to `tts_qwen.py` or `tts_instance.py` affect all audio generation globally.
- **Anti-scrape list in base.py** — these strings must be exact matches of messages found on source sites. Do not reformat or deduplicate without verifying.
- **FFmpeg commands** — audio utils shell out to ffmpeg. Test changes with actual audio files.
- **Speaker files** — voice profiles in `speakers/` are WAV files used for voice cloning. Names must match narrator/mapping values in config (without extension).
- **ChapterDB is source of truth for processing state** — `sync_filesystem` reconciles DB with disk (registers new files, reverts missing outputs, cleans orphaned entries). The DB lives at `{output_dir}/audiobook.db`.
- **GUI runs pipeline on the JobQueue's single daemon worker thread** — pipeline work serializes through the queue; interactive flows that bypass the queue (rescrape preview, filename fixes, resync, sync) are guarded by `is_busy` checks (409 in the API).
- **frontend/dist is committed** — after editing `frontend/src/`, always `npm run build` and commit the refreshed dist, or `uv run audiobook` serves a stale UI.

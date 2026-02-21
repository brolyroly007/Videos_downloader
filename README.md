<p align="center">
  <h1 align="center">Videos Downloader</h1>
  <p align="center">
    <strong>Automated Viral Content Pipeline</strong> &mdash; Download, process, and upload viral videos across platforms.
  </p>
</p>

<p align="center">
  <a href="#features">Features</a> &bull;
  <a href="#tech-stack">Tech Stack</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#docker-deployment">Docker</a> &bull;
  <a href="#api-reference">API</a> &bull;
  <a href="#documentation">Docs</a> &bull;
  <a href="#license">License</a>
</p>

<p align="center">
  <a href="https://github.com/brolyroly007/Videos_downloader/actions/workflows/ci.yml"><img src="https://github.com/brolyroly007/Videos_downloader/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/brolyroly007/Videos_downloader/actions/workflows/docker.yml"><img src="https://github.com/brolyroly007/Videos_downloader/actions/workflows/docker.yml/badge.svg" alt="Docker Build"></a>
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white" alt="Next.js 16">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT"></a>
</p>

---

## Overview

**Videos Downloader** is a full-stack automation platform that discovers, downloads, processes, and uploads viral short-form videos. It supports multiple source platforms and automates the entire content pipeline from URL to TikTok upload with a single click.

## Features

### Multi-Platform Download
- **TikTok** &mdash; watermark-free downloads
- **Instagram Reels** &mdash; direct reel extraction
- **YouTube Shorts** &mdash; high-quality download
- **Facebook Watch** &mdash; video extraction

### Video Processing
- Re-frame to **9:16 vertical** format (optimized for short-form platforms)
- **Blurred** or **solid color** backgrounds for non-vertical videos
- **Anti-copyright effects**: horizontal mirror, speed adjustment (1.02x), color tone shift
- Audio and video quality preservation

### AI-Powered Subtitles
- **OpenAI Whisper** automatic speech recognition
- Multi-language transcription support
- `.srt` subtitle generation
- Burn subtitles into video with customizable font, size, color, and stroke
- GPU acceleration (CUDA) when available

### Automated TikTok Upload
- **Playwright**-based browser automation
- Cookie-based session persistence (login once, upload forever)
- Human behavior simulation to avoid bot detection
- Automatic caption and hashtag insertion

### Viral Content Intelligence
- Viral score calculation based on engagement metrics
- Trending hashtag detection and recommendation
- AI-powered description generation (OpenAI GPT / local Ollama)

### Advanced Platform Features
- **Job Queue System** &mdash; parallel processing with priority management (3 workers)
- **Analytics Dashboard** &mdash; track views, likes, upload success rates
- **Automatic Backups** &mdash; 7-day rolling database backups
- **Role-Based Auth** &mdash; admin, user, and viewer roles
- **Modern Frontend** &mdash; Next.js 16 + React 19 dashboard with dark mode

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Frontend** | Next.js 16, React 19, Tailwind CSS v4, Radix UI |
| **Video** | FFmpeg, MoviePy, OpenCV |
| **AI/ML** | OpenAI Whisper, Ollama (optional) |
| **Automation** | Playwright, Selenium |
| **Download** | yt-dlp |
| **Database** | SQLite (5 databases) |
| **Cache** | Redis |
| **Containers** | Docker, Docker Compose |

## Project Structure

```
Videos_downloader/
├── app.py                          # FastAPI main application
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── Dockerfile                      # Backend container
├── docker-compose.yml              # Multi-service orchestration
│
├── modules/                        # Core Python modules
│   ├── downloader.py               # Multi-platform video download
│   ├── video_processor.py          # Video effects & reframing
│   ├── subtitle_generator.py       # Whisper AI transcription
│   ├── uploader.py                 # TikTok upload automation
│   ├── viral_detector.py           # Viral score analysis
│   ├── automation_engine.py        # Batch job coordination
│   ├── description_generator.py    # AI caption generation
│   ├── hashtag_recommender.py      # Trending hashtag engine
│   ├── queue_manager.py            # Parallel job queue
│   ├── backup_manager.py           # Automated backup system
│   ├── analytics.py                # Statistics tracking
│   ├── auth.py                     # Authentication & authorization
│   └── tiktok_discover.py          # TikTok feed discovery
│
├── frontend/                       # Next.js 16 dashboard
│   ├── src/
│   │   ├── app/                    # App router pages
│   │   └── components/             # React components
│   ├── Dockerfile                  # Frontend container
│   └── package.json
│
├── templates/
│   └── index.html                  # Legacy Jinja2 dashboard
│
├── tests/                          # pytest test suite
│   ├── test_api.py                 # API endpoint tests
│   ├── test_downloader.py          # Downloader module tests
│   ├── test_video_processor.py     # Video processor tests
│   └── test_viral_detector.py      # Viral detector tests
│
├── docs/                           # Additional documentation
│   ├── COOKIES_GUIDE.md            # Cookie export instructions
│   └── TIKTOK_TROUBLESHOOTING.md   # TikTok download solutions
│
├── scripts/                        # Utility scripts
│   ├── install.sh / install.bat    # Setup script
│   ├── run.sh / run.bat            # Start backend
│   └── start_all.sh / start_all.bat # Start all services
│
├── .github/                        # GitHub configuration
│   ├── workflows/ci.yml            # CI pipeline (lint + test)
│   ├── workflows/docker.yml        # Docker build validation
│   ├── ISSUE_TEMPLATE/             # Bug report & feature request
│   └── PULL_REQUEST_TEMPLATE.md    # PR template
│
├── Makefile                        # Task runner (make test, make lint...)
├── pyproject.toml                  # Project config, ruff, pytest
└── .pre-commit-config.yaml         # Pre-commit hooks
```

## Quick Start

### Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.8 or higher |
| **FFmpeg** | Required for video processing ([download](https://ffmpeg.org/download.html)) |
| **Node.js** | 18+ (only for frontend development) |
| **GPU** | Optional &mdash; NVIDIA GPU accelerates Whisper AI |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/brolyroly007/Videos_downloader.git
cd Videos_downloader

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
playwright install chromium

# 5. Configure environment (optional)
cp .env.example .env
# Edit .env to customize settings
```

### FFmpeg Setup (Windows)

1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH
4. Verify: `ffmpeg -version`

### Run the Application

```bash
# Start the backend server
python app.py

# Or with uvicorn (hot reload)
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at **http://localhost:8000**

### GPU Setup (Optional &mdash; Faster Whisper)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Docker Deployment

The project includes a complete Docker Compose setup with 4 services:

| Service | Port | Description |
|---|---|---|
| **Backend** | 8000 | FastAPI application |
| **Frontend** | 3000 | Next.js dashboard |
| **Redis** | 6379 | Cache layer |
| **Backup** | &mdash; | Automated daily backups |

```bash
# Build and start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

## Usage

### Web Dashboard

1. **Paste a URL** &mdash; from TikTok, Instagram, YouTube Shorts, or Facebook
2. **Preview** (optional) &mdash; click Preview to see video info before downloading
3. **Configure options**:
   - Re-frame to 9:16
   - Background type (blur / solid color)
   - Anti-copyright effects (mirror, speed)
   - AI subtitles (language selection)
4. **Add description** &mdash; write your TikTok caption with hashtags
5. **Process**:
   - *"Process Video"* &mdash; download and process only
   - *"Process & Upload to TikTok"* &mdash; full automated pipeline

### First TikTok Upload

On the first upload:
1. A browser window will open automatically
2. **Log in to TikTok manually**
3. Cookies are saved for future sessions
4. All subsequent uploads are fully automatic

To reset your session, click **"Clear Session"** in the dashboard.

## API Reference

### Information

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/info` | Application status & info |
| `GET` | `/api/video-info?url=<URL>` | Preview video metadata |

### Processing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/download` | Download video only |
| `POST` | `/api/process` | Process a downloaded video |
| `POST` | `/api/upload` | Upload to TikTok |
| `POST` | `/api/complete-flow` | Full pipeline: download + process + upload |

### Files

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/files/downloads` | List downloaded videos |
| `GET` | `/api/files/processed` | List processed videos |

### Session

| Method | Endpoint | Description |
|---|---|---|
| `DELETE` | `/api/clear-session` | Clear TikTok session cookies |

### Example: Complete Flow

```bash
curl -X POST http://localhost:8000/api/complete-flow \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@user/video/1234567890",
    "reframe": true,
    "background_type": "blur",
    "mirror": true,
    "speed_factor": 1.02,
    "generate_subtitles": true,
    "language": "es",
    "description": "Check this out! #viral #fyp"
  }'
```

## Configuration

All settings can be customized via the `.env` file:

```env
# Server
HOST=0.0.0.0
PORT=8000

# AI Model (tiny | base | small | medium | large)
WHISPER_MODEL_SIZE=base

# Video Defaults
DEFAULT_WIDTH=1080
DEFAULT_HEIGHT=1920
DEFAULT_FPS=30
DEFAULT_SPEED_FACTOR=1.02

# Subtitle Styling
DEFAULT_FONT_SIZE=70
DEFAULT_FONT_COLOR=yellow
DEFAULT_STROKE_COLOR=black
DEFAULT_STROKE_WIDTH=4

# TikTok Upload
TIKTOK_HEADLESS=false
TIKTOK_LOGIN_TIMEOUT=300000
```

## Documentation

- [Cookie Export Guide](docs/COOKIES_GUIDE.md) &mdash; how to export TikTok cookies for downloading
- [TikTok Troubleshooting](docs/TIKTOK_TROUBLESHOOTING.md) &mdash; solutions for TikTok download issues

## Troubleshooting

| Problem | Solution |
|---|---|
| `FFmpeg not found` | Install FFmpeg and add to PATH. Restart terminal after. |
| Whisper is slow | Use `tiny` or `base` model. Enable GPU if available. |
| TikTok CAPTCHA | Normal on first upload. Solve manually. Space out uploads. |
| No audio after processing | Check original video has audio. Review FFmpeg logs. |
| TikTok download fails | Update yt-dlp: `pip install -U yt-dlp`. See [troubleshooting guide](docs/TIKTOK_TROUBLESHOOTING.md). |

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) before submitting a pull request.

## Legal Disclaimer

- Respect copyright laws and content ownership
- Only use this tool with content you have the right to use
- Comply with each platform's terms of service
- Automated uploading may violate TikTok's ToS &mdash; use at your own risk
- This project is for **educational and research purposes**

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with Python, FastAPI, Whisper AI, Playwright & Next.js
</p>

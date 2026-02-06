# youtube-napoletano

[![CI](https://github.com/ltpitt/youtube-napoletano/actions/workflows/ci.yml/badge.svg)](https://github.com/ltpitt/youtube-napoletano/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## About

**youtube-napoletano** is a web service for downloading YouTube videos and audio, powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and Flask.  
It’s designed to help you skip the boring, annoying ads and get straight to the content you want. Fast, simple, and with a smile.

### Why "Napoletano"?

Naples is famous for its creativity and street smarts qualities that inspired this project’s clever approach to YouTube downloads.  
The name is a playful tribute, not meant to offend, but to celebrate the legendary ingenuity of Neapolitan people.  
If you’re from Naples or just love a good workaround, we hope you’ll smile at the spirit behind the name!

> “A' lietto astritto, cuccate ammiezo.”

_When the bed is tight, sleep in the middle. In other words: when life (or YouTube) gives you little room, find the clever spot!_


## Features

- Download YouTube videos or extract audio (MP3)
- Progress bar and status updates via web UI
- One-click yt-dlp updater
- No ads, no nonsense

---

### Hypothetical Use Case: Synology NAS

While this script is for didactic and personal use only, it could "hypothetically" be run on a Synology NAS (or similar home server). In such a setup, the NAS might automatically share the downloaded videos with your living room TV or other devices on your home network—making it easy for everyone to enjoy content ad-free, right from the couch!

_Please use this script only for didactic and personal purposes, and always respect YouTube’s Terms of Service and your local laws._

## Quickstart

### Requirements

- Python 3.12+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Flask

### Installation

```sh
git clone https://github.com/ltpitt/youtube-napoletano.git
cd youtube-napoletano
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Usage

#### With Make (recommended)

```sh
make run
```

#### Without Make

```sh
# Create virtual environment if not already present
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Run the app
.venv/bin/python youtube_napoletano.py
```

Then open [http://localhost:8443](http://localhost:8443) in your browser.

## Development

- **Lint:** `make lint` or `.venv/bin/ruff check .`
- **Format:** `make format` or `.venv/bin/ruff format .`
- **Install deps:** `make install` or `python3.12 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt`
- **Clean:** `make clean` or `find . -type d -name "__pycache__" -exec rm -rf {} + && rm -rf .venv`

## Configuration

Copy `config.py.example` to `youtube_napoletano/config.py` and adjust paths as needed:

```sh
cp config.py.example youtube_napoletano/config.py
```

Configuration options:
- `YTDLP_PATH`: Path to yt-dlp executable (default: `.venv/bin/yt-dlp`)
- `PYTHON_PATH`: Path to Python executable (default: `.venv/bin/python3`)
- `OUTPUT_DIR`: Download directory (default: `./downloads`)
- `UPDATE_TIMESTAMP_FILE`: Path to yt-dlp update timestamp file

You can also set these via environment variables.

## Contributing

Pull requests are welcome!  
Please open an issue first to discuss what you would like to change.

## License

[GPLv3](LICENSE)

---

## Troubleshooting

If downloads suddenly stop working or you see errors related to YouTube extraction, it's likely that YouTube has updated their site. In most cases, updating `yt-dlp` will resolve the issue.

- **Recommended:** Use the "Update yt-dlp" button in the web interface. This is the easiest and safest way to update.

If problems persist, check the [yt-dlp GitHub page](https://github.com/yt-dlp/yt-dlp) for updates or open an issue.

---

_This project is for educational and personal use. Please respect YouTube’s Terms of Service and your local laws._
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from flask import current_app
import re

from youtube_napoletano.config import PYTHON_PATH, UPDATE_TIMESTAMP_FILE, YTDLP_PATH


def run_yt_dlp_command(
    command: list[str],
    capture_output: bool = True,
    check: bool = True,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, capture_output=capture_output, text=True, check=check, timeout=timeout
    )


def parse_progress(line: str) -> Optional[Dict[str, str]]:
    match = re.search(
        r"\[download\]\s+(\d+\.?\d*)%\s+of\s+(\d+\.?\d*\w+iB)\s+at\s+(\d+\.?\d*\w+iB/s)\s+ETA\s+(\d+:\d+)",
        line,
    )
    if match:
        return {
            "percent": match.group(1),
            "size": match.group(2),
            "speed": match.group(3),
            "eta": match.group(4),
        }
    match_simple = re.search(
        r"\[download\]\s+(\d+\.?\d*)%\s+of\s+(\d+\.?\d*\w+iB)", line
    )
    if match_simple:
        return {
            "percent": match_simple.group(1),
            "size": match_simple.group(2),
            "speed": "N/A",
            "eta": "N/A",
        }
    return None


def update_ytdlp() -> None:
    try:
        run_yt_dlp_command(
            [PYTHON_PATH, YTDLP_PATH, "--no-check-certificate", "-U"],
            timeout=30,
            check=False,
        )
        Path(UPDATE_TIMESTAMP_FILE).write_text(datetime.now().isoformat())
        current_app.logger.info("yt-dlp updated successfully")
    except Exception as e:
        current_app.logger.warning(f"yt-dlp update failed (continuing anyway): {e}")


def fetch_metadata(url: str, timeout: int = 90) -> dict:
    """Fetch video title and thumbnail using curl and meta tags (fastest).

    Returns a dict with keys: title, thumbnail.
    Raises RuntimeError on failure.
    """
    command = ["curl", "-s", "-L", url]
    try:
        proc = run_yt_dlp_command(
            command, capture_output=True, check=True, timeout=timeout
        )
        html = proc.stdout
        # Extract og:title
        title_match = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if not title_match:
            title_match = re.search(r"<title>([^<]*)</title>", html)
        if not title_match:
            raise RuntimeError("No title found in page")
        title = title_match.group(1)

        # Extract og:image (thumbnail)
        thumbnail = None
        thumbnail_match = re.search(
            r'<meta property="og:image" content="([^"]*)"', html
        )
        if thumbnail_match:
            thumbnail = thumbnail_match.group(1)

        return {
            "title": title,
            "thumbnail": thumbnail,
        }
    except subprocess.CalledProcessError as e:
        current_app.logger.debug(f"curl fetch failed: {e}")
        raise RuntimeError("Failed to fetch page")
    except Exception as e:
        current_app.logger.debug(f"metadata fetch error: {e}")
        raise RuntimeError("Failed to fetch metadata")

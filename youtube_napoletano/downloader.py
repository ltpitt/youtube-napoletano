import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from flask import current_app

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
    import re

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
        run_yt_dlp_command([PYTHON_PATH, YTDLP_PATH, "--no-check-certificate", "-U"], timeout=30, check=False)
        Path(UPDATE_TIMESTAMP_FILE).write_text(datetime.now().isoformat())
        current_app.logger.info("yt-dlp updated successfully")
    except Exception as e:
        current_app.logger.warning(f"yt-dlp update failed (continuing anyway): {e}")


def fetch_metadata(url: str, timeout: int = 15) -> dict:
    """Fetch basic video metadata using yt-dlp JSON output.

    Returns a dict with keys: title, description, thumbnail, webpage_url.
    Raises RuntimeError on failure.
    """
    import json

    command = [PYTHON_PATH, YTDLP_PATH, "-j", "--no-check-certificate", url]
    try:
        proc = run_yt_dlp_command(command, capture_output=True, check=True, timeout=timeout)
        out = proc.stdout.strip()
        if not out:
            raise RuntimeError("No metadata returned")
        first = out.splitlines()[0]
        data = json.loads(first)
        return {
            "title": data.get("title"),
            "description": data.get("description"),
            "thumbnail": data.get("thumbnail"),
            "webpage_url": data.get("webpage_url") or url,
        }
    except subprocess.CalledProcessError as e:
        current_app.logger.debug(f"yt-dlp metadata fetch failed: {e}")
        raise RuntimeError("yt-dlp failed to fetch metadata")
    except Exception as e:
        current_app.logger.debug(f"metadata parse error: {e}")
        raise RuntimeError("Failed to parse metadata")

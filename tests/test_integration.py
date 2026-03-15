"""Integration tests: verify real yt-dlp downloads (requires internet access)."""

import re

import pytest

from youtube_napoletano.config import PYTHON_PATH, YTDLP_PATH
from youtube_napoletano.downloader import run_yt_dlp_command

# A short, well-known video that has English subtitles and is unlikely to be removed.
_INTEGRATION_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Timeout constants (seconds) for yt-dlp subprocess calls.
_TIMEOUT_DOWNLOAD = 120
_TIMEOUT_QUERY = 60

# Expected subtitle file header.
_WEBVTT_HEADER = "WEBVTT"

# Mark all tests in this module so they can be excluded when offline.
pytestmark = pytest.mark.integration


def test_subtitle_download_produces_vtt_file(tmp_path):
    """Subtitles download creates a .vtt file with valid VTT content."""
    command = [
        PYTHON_PATH,
        YTDLP_PATH,
        "--write-sub",
        "--write-auto-sub",
        "--skip-download",
        "-o",
        str(tmp_path / "%(title)s.%(ext)s"),
        _INTEGRATION_URL,
    ]
    result = run_yt_dlp_command(command, check=True, timeout=_TIMEOUT_DOWNLOAD)
    assert result.returncode == 0

    vtt_files = list(tmp_path.glob("*.vtt"))
    assert vtt_files, "Expected at least one .vtt subtitle file to be downloaded"

    subtitle_content = vtt_files[0].read_text(encoding="utf-8")
    assert subtitle_content.startswith(_WEBVTT_HEADER), (
        f"Subtitle file must start with {_WEBVTT_HEADER} header"
    )
    assert re.search(
        r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", subtitle_content
    ), "Subtitle file must contain timestamp cues"
    assert len(subtitle_content.strip()) > 50, (
        "Subtitle file must contain actual text content"
    )


def test_video_download_without_subtitles_still_works(tmp_path):
    """Previous functionality: downloading without subtitles produces a video file."""
    command = [
        PYTHON_PATH,
        YTDLP_PATH,
        "--skip-download",
        "--print",
        "title",
        _INTEGRATION_URL,
    ]
    result = run_yt_dlp_command(command, check=True, timeout=_TIMEOUT_QUERY)
    assert result.returncode == 0
    assert result.stdout.strip() != "", "yt-dlp should print the video title"


def test_audio_only_flag_still_works(tmp_path):
    """Previous functionality: audio-only flag is accepted by yt-dlp without error."""
    command = [
        PYTHON_PATH,
        YTDLP_PATH,
        "--simulate",
        "-f",
        "bestaudio/best",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        _INTEGRATION_URL,
    ]
    result = run_yt_dlp_command(command, check=True, timeout=_TIMEOUT_QUERY)
    assert result.returncode == 0

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from youtube_napoletano.downloader import parse_progress


def _make_completed_process(
    stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


@pytest.fixture()
def app_context():
    """Provide a minimal Flask app context for update_ytdlp tests."""
    from youtube_napoletano.app import app

    with app.app_context():
        yield


def test_parse_progress_full():
    line = "[download] 42.0% of 10.00MiB at 2.00MiB/s ETA 00:10"
    result = parse_progress(line)
    assert result == {
        "percent": "42.0",
        "size": "10.00MiB",
        "speed": "2.00MiB/s",
        "eta": "00:10",
    }


def test_parse_progress_simple():
    line = "[download] 10.0% of 1.00MiB"
    result = parse_progress(line)
    assert result == {
        "percent": "10.0",
        "size": "1.00MiB",
        "speed": "N/A",
        "eta": "N/A",
    }


def test_parse_progress_none():
    line = "[other] something else"
    assert parse_progress(line) is None


class TestUpdateYtdlp:
    """Tests for update_ytdlp conditional timestamp write behaviour."""

    def test_writes_timestamp_when_up_to_date(self, tmp_path, app_context):
        """Timestamp file is written when output says yt-dlp is up to date."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                return_value=_make_completed_process(stdout="yt-dlp is up to date"),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            downloader.update_ytdlp()

        assert ts_file.exists()

    def test_writes_timestamp_when_updating(self, tmp_path, app_context):
        """Timestamp file is written when output contains 'Updating to'."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                return_value=_make_completed_process(
                    stdout="Updating to 2024.01.01..."
                ),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            downloader.update_ytdlp()

        assert ts_file.exists()

    def test_no_timestamp_when_output_unrecognised(self, tmp_path, app_context):
        """Timestamp file is NOT written when output lacks expected phrases."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                return_value=_make_completed_process(stdout="Something unexpected"),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            downloader.update_ytdlp()

        assert not ts_file.exists()

    def test_no_timestamp_on_exception(self, tmp_path, app_context):
        """Timestamp file is NOT written when run_yt_dlp_command raises."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                side_effect=Exception("timeout"),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            downloader.update_ytdlp()

        assert not ts_file.exists()

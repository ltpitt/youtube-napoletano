import subprocess
from unittest.mock import MagicMock, patch

import pytest

from youtube_napoletano.downloader import parse_progress


def _make_completed_process(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
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
    """Tests for update_ytdlp pip-based upgrade behaviour."""

    def test_upgrades_via_pip_and_writes_timestamp_on_success(
        self, tmp_path, app_context
    ):
        """On pip success (exit 0) the timestamp is written using a pip command."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                return_value=_make_completed_process(returncode=0),
            ) as mock_run,
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            downloader.update_ytdlp()

        assert ts_file.exists()
        command = mock_run.call_args.args[0]
        assert "pip" in command
        assert "install" in command
        assert "--upgrade" in command

    def test_raises_and_no_timestamp_when_pip_fails(self, tmp_path, app_context):
        """A non-zero pip exit raises and does NOT write the timestamp."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                return_value=_make_completed_process(
                    returncode=1, stderr="ERROR: could not install"
                ),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            with pytest.raises(RuntimeError):
                downloader.update_ytdlp()

        assert not ts_file.exists()

    def test_raises_and_no_timestamp_on_exception(self, tmp_path, app_context):
        """When the pip command cannot run, update_ytdlp raises RuntimeError."""
        from youtube_napoletano import downloader

        ts_file = tmp_path / "ts.txt"
        with (
            patch.object(
                downloader,
                "run_yt_dlp_command",
                side_effect=OSError("python not found"),
            ),
            patch.object(downloader, "UPDATE_TIMESTAMP_FILE", str(ts_file)),
        ):
            with pytest.raises(RuntimeError):
                downloader.update_ytdlp()

        assert not ts_file.exists()

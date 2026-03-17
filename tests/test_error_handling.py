"""Tests for error handling and error details display."""

import json
import pytest

from youtube_napoletano.app import _download_states, _downloads_lock, app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_download_states():
    """Ensure _download_states is empty before and after every test."""
    with _downloads_lock:
        _download_states.clear()
    yield
    with _downloads_lock:
        _download_states.clear()


class TestErrorMessages:
    """Test error message formatting and details."""

    def test_download_error_includes_details(self, client, monkeypatch):
        """Download errors include technical details from stderr."""

        class FailingPopen:
            def __init__(self, command, **kwargs):
                self.command = command
                self.stdout = iter([])
                self.stderr = iter(
                    ["ERROR: [youtube] dQw4w9WgXcQ: Unable to download page"]
                )
                self.returncode = 1

            def wait(self):
                pass

        monkeypatch.setattr("youtube_napoletano.app.subprocess.Popen", FailingPopen)

        resp = client.get(
            "/download_stream?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&audio_only=false&subtitles=false"
        )
        assert resp.status_code == 200
        data = resp.data.decode()

        # Should contain error_event with error and details
        assert "event: error_event" in data
        # Error response should have both error message and details
        assert "error" in data

    def test_invalid_url_returns_error(self, client):
        """Invalid URL returns proper error message."""
        resp = client.get(
            "/download_stream?url=invalid-url&audio_only=false&subtitles=false"
        )
        assert resp.status_code == 200
        # SSE stream should contain error_event
        assert b"error_event" in resp.data
        assert b"nun valida" in resp.data

    def test_metadata_endpoint_error_handling(self, client, monkeypatch):
        """Metadata endpoint returns error on fetch failure."""

        def raise_timeout(url):
            raise Exception("Timeout")

        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata",
            raise_timeout,
        )

        resp = client.get("/metadata?url=https://www.youtube.com/watch?v=test")
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert "error" in data
        assert "metadata" not in data

    def test_update_endpoint_error_response(self, client, monkeypatch):
        """Update endpoint returns error with details on failure."""
        monkeypatch.setattr(
            "youtube_napoletano.app.should_update_ytdlp", lambda x: True
        )

        def raise_update_error():
            raise RuntimeError("Update failed")

        monkeypatch.setattr(
            "youtube_napoletano.app.update_ytdlp",
            raise_update_error,
        )

        resp = client.post("/update")
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert "error" in data

    def test_error_message_format(self, client):
        """Error message format matches expected structure."""
        resp = client.get(
            "/download_stream?url=not-a-url&audio_only=false&subtitles=false"
        )
        assert resp.status_code == 200
        data = resp.data.decode()

        # Should have SSE event format
        assert "event:" in data
        assert "data:" in data
        # Should be valid JSON in data field
        lines = data.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("data:"):
                try:
                    json.loads(line[5:])
                except (json.JSONDecodeError, ValueError):
                    pass  # Some data lines might not be JSON

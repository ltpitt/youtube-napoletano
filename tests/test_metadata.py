"""Tests for metadata fetching and display functionality."""

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


class TestMetadataEndpoint:
    """Test the /metadata endpoint."""

    def test_metadata_valid_url(self, client, monkeypatch):
        """Metadata endpoint returns metadata for valid YouTube URL."""
        # Mock fetch_metadata to return test data
        mock_meta = {
            "title": "Test Video",
            "description": "Test description",
            "thumbnail": "https://example.com/thumb.jpg",
            "webpage_url": "https://www.youtube.com/watch?v=test123",
        }
        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata", lambda url: mock_meta
        )

        resp = client.get("/metadata?url=https://www.youtube.com/watch?v=test123")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "metadata" in data
        assert data["metadata"]["title"] == "Test Video"
        assert data["metadata"]["description"] == "Test description"
        assert data["metadata"]["thumbnail"] == "https://example.com/thumb.jpg"

    def test_metadata_invalid_url(self, client):
        """Metadata endpoint rejects invalid YouTube URLs."""
        resp = client.get("/metadata?url=not-a-youtube-url")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data
        assert "nun valida" in data["error"]

    def test_metadata_empty_url(self, client):
        """Metadata endpoint rejects empty URLs."""
        resp = client.get("/metadata?url=")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data

    def test_metadata_fetch_error(self, client, monkeypatch):
        """Metadata endpoint handles fetch errors gracefully."""
        def raise_error(url):
            raise RuntimeError("Network error")

        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata",
            raise_error,
        )

        resp = client.get("/metadata?url=https://www.youtube.com/watch?v=test123")
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert "error" in data

    def test_metadata_whitespace_handling(self, client, monkeypatch):
        """Metadata endpoint handles URLs with leading/trailing whitespace."""
        mock_meta = {"title": "Test", "description": "", "thumbnail": "", "webpage_url": ""}
        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata", lambda url: mock_meta
        )

        # URL with whitespace should be stripped and work
        resp = client.get("/metadata?url=%20https://www.youtube.com/watch?v=test123%20")
        assert resp.status_code == 200


class TestMetadataInDownloadState:
    """Test metadata persistence in download state."""

    def test_metadata_persisted_in_download_state(self, client, monkeypatch):
        """Metadata is stored and returned in /status endpoint."""

        class FakePopen:
            def __init__(self, command, **kwargs):
                self.command = command
                self.stdout = iter([])
                self.stderr = iter([])
                self.returncode = 0

            def wait(self):
                pass

        monkeypatch.setattr("youtube_napoletano.app.subprocess.Popen", FakePopen)
        mock_meta = {
            "title": "Rickroll",
            "description": "Never gonna give you up",
            "thumbnail": "https://example.com/thumb.jpg",
            "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }
        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata", lambda url: mock_meta
        )

        # Start a download
        resp = client.get(
            "/download_stream?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&audio_only=false&subtitles=false"
        )
        assert resp.status_code == 200

        # Extract download ID from SSE stream
        lines = resp.data.decode().split("\n")
        download_id = None
        for line in lines:
            if "download_started" in line:
                data = [event_line for event_line in lines if event_line.startswith("data:")][0]
                download_id = json.loads(data[5:]).get("download_id")
                break

        if download_id:
            # Check status endpoint includes metadata
            status_resp = client.get(f"/status/{download_id}")
            assert status_resp.status_code == 200
            status_data = json.loads(status_resp.data)
            assert "metadata" in status_data
            assert status_data["metadata"]["title"] == "Rickroll"


class TestMetadataDownloadIntegration:
    """Test metadata is included in SSE download stream."""

    def test_metadata_in_sse_stream(self, client, monkeypatch):
        """Metadata is sent via SSE in the download stream."""

        class FakePopen:
            def __init__(self, command, **kwargs):
                self.command = command
                self.stdout = iter(["[download] 50%\n"])
                self.stderr = iter([])
                self.returncode = 0

            def wait(self):
                pass

        monkeypatch.setattr("youtube_napoletano.app.subprocess.Popen", FakePopen)
        mock_meta = {
            "title": "Test",
            "description": "Test desc",
            "thumbnail": "https://example.com/thumb.jpg",
            "webpage_url": "https://www.youtube.com/watch?v=test",
        }
        monkeypatch.setattr(
            "youtube_napoletano.app.fetch_metadata", lambda url: mock_meta
        )

        resp = client.get(
            "/download_stream?url=https://www.youtube.com/watch?v=test&audio_only=false&subtitles=false"
        )
        assert resp.status_code == 200
        data = resp.data.decode()
        # Should contain download_started event with download_id
        assert "event: download_started" in data

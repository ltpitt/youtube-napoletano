import pytest

from youtube_napoletano.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"YouTube Napulitano" in resp.data


def test_update_endpoint(client, monkeypatch):
    monkeypatch.setattr("youtube_napoletano.downloader.update_ytdlp", lambda: None)
    monkeypatch.setattr("youtube_napoletano.utils.should_update_ytdlp", lambda x: True)
    resp = client.post("/update")
    assert resp.status_code == 200
    assert (
        b"yt-dlp aggiurnato" in resp.data
        or b"yt-dlp is already up to date" in resp.data
    )


def test_download_stream_invalid_url(client):
    resp = client.get("/download_stream?url=invalid&audio_only=false")
    assert resp.status_code == 200
    assert b"URL nun valida" in resp.data


def test_download_stream_invalid_url_with_subtitles(client):
    resp = client.get("/download_stream?url=invalid&audio_only=false&subtitles=true")
    assert resp.status_code == 200
    assert b"URL nun valida" in resp.data


def test_download_invalid_url(client):
    resp = client.post("/download", data={"url": "invalid"})
    assert resp.status_code == 400
    assert b"URL nun valida" in resp.data


def test_index_has_subtitles_checkbox(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"subtitles" in resp.data
    assert b"sottotitole" in resp.data


def test_download_with_subtitles_passes_flags(client, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        import subprocess

        result = subprocess.CompletedProcess(command, 0, "", "")
        return result

    monkeypatch.setattr("youtube_napoletano.downloader.run_yt_dlp_command", fake_run)
    resp = client.post(
        "/download",
        data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "subtitles": "on"},
    )
    assert resp.status_code == 200
    assert "--write-sub" in captured["command"]
    assert "--write-auto-sub" in captured["command"]


def test_download_stream_with_subtitles_passes_flags(client, monkeypatch):
    import subprocess as _subprocess

    captured = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            self.stdout = iter([])
            self.returncode = 0

        def wait(self):
            pass

    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.get(
        "/download_stream"
        "?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&audio_only=false&subtitles=true"
    )
    resp.get_data()  # consume stream to trigger the generator
    assert "--write-sub" in captured.get("command", [])
    assert "--write-auto-sub" in captured.get("command", [])


def test_download_audio_only_flags_after_ytdlp_path(client, monkeypatch):
    """Regression: -f and audio flags must appear after YTDLP_PATH, not before it."""
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        import subprocess

        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("youtube_napoletano.downloader.run_yt_dlp_command", fake_run)
    resp = client.post(
        "/download",
        data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "audio_only": "on"},
    )
    assert resp.status_code == 200
    cmd = captured["command"]
    # YTDLP_PATH is always at index 1; -f must appear after it
    from youtube_napoletano.config import YTDLP_PATH

    assert cmd.index("-f") > cmd.index(YTDLP_PATH), "-f must come after YTDLP_PATH"
    assert "-x" in cmd
    assert "--audio-format" in cmd

import pytest
from youtube_napoletano import app

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
    monkeypatch.setattr("downloader.update_ytdlp", lambda: None)
    monkeypatch.setattr("utils.should_update_ytdlp", lambda x: True)
    resp = client.post("/update")
    assert resp.status_code == 200
    assert b"yt-dlp aggiurnato" in resp.data or b"yt-dlp is already up to date" in resp.data

def test_download_stream_invalid_url(client):
    resp = client.get("/download_stream?url=invalid&audio_only=false")
    assert resp.status_code == 200
    assert b"URL nun valida" in resp.data

def test_download_invalid_url(client):
    resp = client.post("/download", data={"url": "invalid"})
    assert resp.status_code == 400
    assert b"URL nun valida" in resp.data

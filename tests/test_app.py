import io
import queue
import subprocess as _subprocess
import threading

import pytest

from youtube_napoletano.app import (
    _download_states,
    _downloads_lock,
    _drain_queue,
    _line_to_sse_events,
    _run_download_thread,
    app,
)


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


# ---------------------------------------------------------------------------
# Helper: a minimal FakePopen whose stdout.readline() behaves correctly
# ---------------------------------------------------------------------------
class FakePopen:
    """Minimal subprocess.Popen replacement for unit tests."""

    def __init__(self, command, **kwargs):
        self.command = command
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self.returncode = 0

    def wait(self):
        pass


# ---------------------------------------------------------------------------
# Existing tests (unchanged in intent, FakePopen now uses io.StringIO)
# ---------------------------------------------------------------------------


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"'O Tubb napulitano" in resp.data


def test_healthz_endpoint(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_update_endpoint(client, monkeypatch):
    monkeypatch.setattr("youtube_napoletano.downloader.update_ytdlp", lambda: None)
    monkeypatch.setattr("youtube_napoletano.utils.should_update_ytdlp", lambda x: True)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: __import__("subprocess").CompletedProcess(
            args=args[0], returncode=0, stdout="", stderr=""
        ),
    )
    resp = client.post("/update")
    assert resp.status_code == 200
    assert b"successo" in resp.data or b"Aggiornamento" in resp.data


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
    captured = {}

    class CapturingFakePopen(FakePopen):
        def __init__(self, command, **kwargs):
            captured["command"] = command
            super().__init__(command, **kwargs)

    monkeypatch.setattr(_subprocess, "Popen", CapturingFakePopen)
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


# ---------------------------------------------------------------------------
# New tests: download_started event
# ---------------------------------------------------------------------------


def test_download_stream_emits_download_started(client, monkeypatch):
    """The first SSE event must be download_started with a non-empty download_id."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.get(
        "/download_stream"
        "?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&audio_only=false&subtitles=false"
    )
    data = resp.get_data(as_text=True)
    assert "event: download_started" in data
    import json
    import re

    match = re.search(r"event: download_started\ndata: (\{.*?\})", data)
    assert match, "download_started event not found in SSE stream"
    payload = json.loads(match.group(1))
    assert "download_id" in payload
    assert len(payload["download_id"]) > 0


# ---------------------------------------------------------------------------
# New tests: /status/<download_id> endpoint
# ---------------------------------------------------------------------------


def test_download_status_not_found(client):
    resp = client.get("/status/nonexistent-id")
    assert resp.status_code == 404
    body = resp.get_json()
    assert "truvato" in body["error"]


def test_download_status_in_progress(client):
    """The /status endpoint reports 'in_progress' for an ongoing download."""
    download_id = "test-in-progress-status"
    with _downloads_lock:
        _download_states[download_id] = {
            "url": "https://www.youtube.com/watch?v=test",
            "status": "in_progress",
            "progress": {
                "percent": "50.0",
                "speed": "1MiB/s",
                "size": "10MiB",
                "eta": "00:05",
            },
            "last_message": "Sto scarricanno...",
            "error": None,
            "queue": queue.Queue(),
        }
    try:
        resp = client.get(f"/status/{download_id}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "in_progress"
        assert body["progress"]["percent"] == "50.0"
        assert body["last_message"] == "Sto scarricanno..."
    finally:
        with _downloads_lock:
            _download_states.pop(download_id, None)


def test_download_status_complete(client, monkeypatch):
    """After the download finishes the status endpoint reports 'complete'."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.get(
        "/download_stream"
        "?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&audio_only=false&subtitles=false"
    )
    data = resp.get_data(as_text=True)

    import json
    import re

    match = re.search(r"event: download_started\ndata: (\{.*?\})", data)
    assert match
    download_id = json.loads(match.group(1))["download_id"]

    status_resp = client.get(f"/status/{download_id}")
    assert status_resp.status_code == 200
    body = status_resp.get_json()
    assert body["status"] == "complete"


# ---------------------------------------------------------------------------
# New tests: SSE reconnect
# ---------------------------------------------------------------------------


def test_download_stream_reconnect_to_complete(client, monkeypatch):
    """Reconnecting to a finished download immediately yields the complete event."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)

    # Trigger a download and wait for it to complete
    first = client.get(
        "/download_stream"
        "?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&audio_only=false&subtitles=false"
    )
    first_data = first.get_data(as_text=True)

    import json
    import re

    match = re.search(r"event: download_started\ndata: (\{.*?\})", first_data)
    assert match
    download_id = json.loads(match.group(1))["download_id"]

    # Reconnect
    second = client.get(f"/download_stream?download_id={download_id}")
    second_data = second.get_data(as_text=True)

    assert "event: complete" in second_data


def test_download_stream_reconnect_not_found(client):
    """Reconnecting with an unknown download_id yields an error_event."""
    resp = client.get("/download_stream?download_id=unknown-id")
    data = resp.get_data(as_text=True)
    assert "event: error_event" in data
    assert "truvato" in data


# ---------------------------------------------------------------------------
# New tests: fire-and-forget behaviour
# ---------------------------------------------------------------------------


def test_download_thread_completes_independently():
    """The background thread runs to completion via its queue regardless of
    whether any SSE generator is consuming the queue."""
    done_event = threading.Event()

    class TrackingFakePopen(FakePopen):
        def wait(self):
            super().wait()
            done_event.set()

    # Manually wire up a state entry and run the thread function directly
    download_id = "test-fire-and-forget"
    task_queue: queue.Queue = queue.Queue()
    with _downloads_lock:
        _download_states[download_id] = {
            "url": "https://www.youtube.com/watch?v=test",
            "status": "in_progress",
            "progress": None,
            "last_message": None,
            "error": None,
            "queue": task_queue,
        }

    # Patch subprocess.Popen for this test
    original_popen = _subprocess.Popen
    _subprocess.Popen = TrackingFakePopen
    try:
        t = threading.Thread(
            target=_run_download_thread,
            args=(download_id, ["fake", "command"]),
            daemon=True,
        )
        t.start()
        t.join(timeout=5)
    finally:
        _subprocess.Popen = original_popen
        with _downloads_lock:
            _download_states.pop(download_id, None)

    assert done_event.is_set(), "Background thread did not complete"


def test_drain_queue_handles_generator_exit():
    """GeneratorExit thrown into _drain_queue must be swallowed so the
    background thread is never interrupted."""
    q: queue.Queue = queue.Queue()
    # Put a line that causes the generator to yield a status event so we can
    # advance it into the try block before closing it.
    q.put(("line", "[download] Destination: test.mp4"))
    gen = _drain_queue("test-disconnect", q)
    # Advance the generator to the first yield (the status event).
    # The generator is now suspended inside the try block.
    event = next(gen)
    assert "event: status" in event
    # Closing here throws GeneratorExit at the current yield point inside the
    # try block; the except GeneratorExit handler must catch it silently.
    gen.close()  # must not raise


def test_line_to_sse_events_progress():
    """A progress line must produce a progress SSE event."""
    line = "[download]  42.0% of 10.00MiB at 1.00MiB/s ETA 00:05"
    events = list(_line_to_sse_events(line))
    assert any("event: progress" in e for e in events)


def test_line_to_sse_events_merger():
    """A merger line must produce a status SSE event."""
    line = "[Merger] Merging formats into output.mp4"
    events = list(_line_to_sse_events(line))
    assert any("event: status" in e for e in events)
    assert any("azzeccanno" in e for e in events)

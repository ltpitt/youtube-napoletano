"""Tests for batch (multi-URL) download feature.

Batch downloads process URLs sequentially with a configurable delay between
each one, so the Synology NAS and YouTube are not overloaded.
"""

import io
import queue
import subprocess as _subprocess
import time

import pytest

from youtube_napoletano.app import (
    _batch_states,
    _batches_lock,
    _download_states,
    _downloads_lock,
    _run_batch_thread,
    app,
)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_states():
    """Ensure shared state dicts are empty before and after every test."""
    with _downloads_lock:
        _download_states.clear()
    with _batches_lock:
        _batch_states.clear()
    yield
    with _downloads_lock:
        _download_states.clear()
    with _batches_lock:
        _batch_states.clear()


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
# /batch endpoint – validation
# ---------------------------------------------------------------------------


def test_batch_rejects_empty_urls(client):
    """POST /batch with no URLs returns 400."""
    resp = client.post("/batch", json={"urls": []})
    assert resp.status_code == 400


def test_batch_rejects_missing_urls(client):
    """POST /batch with no body returns 400."""
    resp = client.post("/batch", json={})
    assert resp.status_code == 400


def test_batch_rejects_invalid_urls(client):
    """POST /batch with non-YouTube URLs returns 400."""
    resp = client.post("/batch", json={"urls": ["https://example.com"]})
    assert resp.status_code == 400


def test_batch_rejects_mixed_valid_invalid(client):
    """POST /batch filters out invalid URLs; if none remain, returns 400."""
    resp = client.post("/batch", json={"urls": ["not-a-url"]})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /batch endpoint – success
# ---------------------------------------------------------------------------


def test_batch_creates_batch_id(client, monkeypatch):
    """POST /batch with valid URLs returns a batch_id and 202."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.post(
        "/batch",
        json={"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]},
    )
    assert resp.status_code == 202
    body = resp.get_json()
    assert "batch_id" in body
    assert len(body["batch_id"]) > 0


def test_batch_accepts_multiple_urls(client, monkeypatch):
    """POST /batch with several valid URLs returns a batch with correct count."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
    ]
    resp = client.post("/batch", json={"urls": urls})
    assert resp.status_code == 202
    body = resp.get_json()
    assert body["total"] == 2


def test_batch_filters_invalid_keeps_valid(client, monkeypatch):
    """POST /batch with a mix of valid and invalid URLs keeps only valid ones."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "not-a-url",
    ]
    resp = client.post("/batch", json={"urls": urls})
    assert resp.status_code == 202
    body = resp.get_json()
    assert body["total"] == 1


def test_batch_passes_audio_only_flag(client, monkeypatch):
    """POST /batch with audio_only=true stores the flag in batch state."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.post(
        "/batch",
        json={
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "audio_only": True,
        },
    )
    body = resp.get_json()
    batch_id = body["batch_id"]
    with _batches_lock:
        state = _batch_states[batch_id]
        assert state["audio_only"] is True


def test_batch_passes_subtitles_flag(client, monkeypatch):
    """POST /batch with subtitles=true stores the flag in batch state."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.post(
        "/batch",
        json={
            "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            "subtitles": True,
        },
    )
    body = resp.get_json()
    batch_id = body["batch_id"]
    with _batches_lock:
        state = _batch_states[batch_id]
        assert state["subtitles"] is True


# ---------------------------------------------------------------------------
# /batch/status/<batch_id> – status endpoint
# ---------------------------------------------------------------------------


def test_batch_status_not_found(client):
    """GET /batch/status/<unknown> returns 404."""
    resp = client.get("/batch/status/nonexistent-id")
    assert resp.status_code == 404


def test_batch_status_in_progress(client, monkeypatch):
    """Status endpoint reports in_progress for a running batch."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    resp = client.post(
        "/batch",
        json={"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]},
    )
    batch_id = resp.get_json()["batch_id"]
    # Give thread a moment to start
    time.sleep(0.2)
    status_resp = client.get(f"/batch/status/{batch_id}")
    assert status_resp.status_code == 200
    body = status_resp.get_json()
    assert body["status"] in ("in_progress", "complete")
    assert "items" in body
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# Batch thread – sequential processing
# ---------------------------------------------------------------------------


def test_batch_thread_processes_sequentially(monkeypatch):
    """The batch thread processes URLs one at a time."""
    call_order = []

    class OrderTrackingPopen(FakePopen):
        def __init__(self, command, **kwargs):
            call_order.append(command[-1])  # URL is the last arg
            super().__init__(command, **kwargs)

    monkeypatch.setattr(_subprocess, "Popen", OrderTrackingPopen)
    monkeypatch.setattr("youtube_napoletano.app.BATCH_DELAY_SECONDS", 0)

    batch_id = "test-sequential"
    urls = [
        "https://www.youtube.com/watch?v=aaa",
        "https://www.youtube.com/watch?v=bbb",
    ]
    task_queue: queue.Queue = queue.Queue()
    with _batches_lock:
        _batch_states[batch_id] = {
            "urls": urls,
            "audio_only": False,
            "subtitles": False,
            "status": "in_progress",
            "current_index": 0,
            "items": [{"url": u, "status": "pending", "error": None} for u in urls],
            "queue": task_queue,
        }

    with app.app_context():
        _run_batch_thread(batch_id)

    assert call_order == [
        "https://www.youtube.com/watch?v=aaa",
        "https://www.youtube.com/watch?v=bbb",
    ]
    with _batches_lock:
        state = _batch_states[batch_id]
        assert state["status"] == "complete"
        assert all(item["status"] == "complete" for item in state["items"])


def test_batch_thread_continues_after_single_failure(monkeypatch):
    """If one URL fails, the batch continues with the remaining URLs."""
    call_count = [0]

    class FailFirstPopen(FakePopen):
        def __init__(self, command, **kwargs):
            call_count[0] += 1
            super().__init__(command, **kwargs)
            if call_count[0] == 1:
                self.returncode = 1
                self.stderr = io.StringIO("Simulated failure")

    monkeypatch.setattr(_subprocess, "Popen", FailFirstPopen)
    monkeypatch.setattr("youtube_napoletano.app.BATCH_DELAY_SECONDS", 0)

    batch_id = "test-continue-after-error"
    urls = [
        "https://www.youtube.com/watch?v=fail",
        "https://www.youtube.com/watch?v=pass",
    ]
    task_queue: queue.Queue = queue.Queue()
    with _batches_lock:
        _batch_states[batch_id] = {
            "urls": urls,
            "audio_only": False,
            "subtitles": False,
            "status": "in_progress",
            "current_index": 0,
            "items": [{"url": u, "status": "pending", "error": None} for u in urls],
            "queue": task_queue,
        }

    with app.app_context():
        _run_batch_thread(batch_id)

    with _batches_lock:
        state = _batch_states[batch_id]
        assert state["status"] == "complete"
        assert state["items"][0]["status"] == "error"
        assert state["items"][1]["status"] == "complete"


def test_batch_thread_respects_delay(monkeypatch):
    """The batch thread waits BATCH_DELAY_SECONDS between downloads."""
    timestamps = []

    class TimingPopen(FakePopen):
        def __init__(self, command, **kwargs):
            timestamps.append(time.monotonic())
            super().__init__(command, **kwargs)

    monkeypatch.setattr(_subprocess, "Popen", TimingPopen)
    monkeypatch.setattr("youtube_napoletano.app.BATCH_DELAY_SECONDS", 0.3)

    batch_id = "test-delay"
    urls = [
        "https://www.youtube.com/watch?v=aaa",
        "https://www.youtube.com/watch?v=bbb",
    ]
    task_queue: queue.Queue = queue.Queue()
    with _batches_lock:
        _batch_states[batch_id] = {
            "urls": urls,
            "audio_only": False,
            "subtitles": False,
            "status": "in_progress",
            "current_index": 0,
            "items": [{"url": u, "status": "pending", "error": None} for u in urls],
            "queue": task_queue,
        }

    with app.app_context():
        _run_batch_thread(batch_id)

    assert len(timestamps) == 2
    # The delay between the two downloads should be >= 0.3s
    assert timestamps[1] - timestamps[0] >= 0.25


# ---------------------------------------------------------------------------
# SSE stream – /batch/stream/<batch_id>
# ---------------------------------------------------------------------------


def test_batch_stream_not_found(client):
    """GET /batch/stream/<unknown> returns an error SSE event."""
    resp = client.get("/batch/stream/nonexistent-id")
    data = resp.get_data(as_text=True)
    assert "event: error_event" in data


def test_batch_stream_emits_events(client, monkeypatch):
    """The batch SSE stream emits batch_item_start and batch_item_complete events."""
    monkeypatch.setattr(_subprocess, "Popen", FakePopen)
    monkeypatch.setattr("youtube_napoletano.app.BATCH_DELAY_SECONDS", 0)

    resp = client.post(
        "/batch",
        json={"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]},
    )
    batch_id = resp.get_json()["batch_id"]
    # Give batch thread time to complete
    time.sleep(0.5)

    stream_resp = client.get(f"/batch/stream/{batch_id}")
    data = stream_resp.get_data(as_text=True)
    # A completed batch should emit a batch_complete event on reconnect
    assert "event: batch_complete" in data or "event: batch_item_complete" in data

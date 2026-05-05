import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Generator

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)

from youtube_napoletano import config
from youtube_napoletano.downloader import parse_progress, update_ytdlp, fetch_metadata
from youtube_napoletano.utils import should_update_ytdlp
from youtube_napoletano.i18n import i18n

# Flask needs to find templates and static in parent directory
template_dir = Path(__file__).parent.parent / "templates"
static_dir = Path(__file__).parent.parent / "static"

app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))

logging.basicConfig(level=logging.DEBUG)

UPDATE_TIMESTAMP_FILE = Path(config.UPDATE_TIMESTAMP_FILE)
YTDLP_PATH = config.YTDLP_PATH
PYTHON_PATH = config.PYTHON_PATH
OUTPUT_DIR = config.OUTPUT_DIR
BATCH_DELAY_SECONDS = getattr(config, "BATCH_DELAY_SECONDS", 5)
YOUTUBE_URL_RE = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$")

def _detect_js_runtime_spec() -> str | None:
    """Detect the best available JS runtime for yt-dlp EJS challenges."""

    # Prefer bundled NAS runtimes inside this repository.
    _runtime_dir = template_dir.parent / "runtimes" / "nas"
    if _runtime_dir.exists():
        for _candidate in sorted(_runtime_dir.glob("**/qjs")):
            if _candidate.is_file() and os.access(_candidate, os.X_OK):
                return f"quickjs:{_candidate}"

    for _rt_name, _rt_bin in (
        ("deno", "deno"),
        ("node", "node"),
        ("bun", "bun"),
    ):
        _rt_path = shutil.which(_rt_bin)
        if _rt_path:
            return _rt_name if _rt_name != "quickjs" else f"quickjs:{_rt_path}"

    # Last fallback: quickjs from PATH.
    _qjs_path = shutil.which("qjs")
    if _qjs_path:
        return f"quickjs:{_qjs_path}"

    return None

# Active download states: download_id -> state dict.
# Kept in memory for the lifetime of the server process so that the GUI can
# reconnect after a browser close / app switch and see the current status.
_download_states: dict[str, dict] = {}
_downloads_lock = threading.Lock()

# Active batch states: batch_id -> state dict.
# Each batch processes URLs sequentially with a delay between downloads.
_batch_states: dict[str, dict] = {}
_batches_lock = threading.Lock()

# Completed download states are evicted from memory after this many seconds.
_STATE_TTL_SECONDS = 3600

# Maximum number of yt-dlp output lines buffered in a download's queue.
# Line events are dropped (without blocking) once the limit is reached; the
# shared state-dict snapshot is always kept current.  Terminal events
# (complete / error / done) are also attempted non-blocking and _drain_queue
# falls back to the state dict so that a reconnecting client never misses them.
_QUEUE_MAXSIZE = 100


def _schedule_eviction(download_id: str) -> None:
    """Remove a finished download from ``_download_states`` after the TTL."""

    def _evict() -> None:
        with _downloads_lock:
            _download_states.pop(download_id, None)
            app.logger.debug(f"Evicted download state {download_id}")

    timer = threading.Timer(_STATE_TTL_SECONDS, _evict)
    timer.daemon = True
    timer.start()


def _start_stderr_drain(process: subprocess.Popen) -> "list[str]":
    """Start a daemon thread that drains the subprocess stderr pipe into a list.

    This prevents the classic pipe-buffer deadlock where the subprocess blocks
    trying to write to stderr while the parent blocks reading from stdout.
    """
    buf: list[str] = []

    def _drain() -> None:
        if process.stderr:
            for line in process.stderr:
                buf.append(line)

    t = threading.Thread(target=_drain, daemon=True)
    t.start()
    return buf


def _run_download_thread(download_id: str, command: list[str]) -> None:
    """Run yt-dlp in a background thread, posting events to a queue.

    The download continues even if the SSE client disconnects (fire-and-forget).
    Progress and status are also stored in ``_download_states`` so that the GUI
    can poll or reconnect at any time and get an up-to-date snapshot.

    All writes to the shared state dict are protected by ``_downloads_lock``
    so readers always see a consistent snapshot.  Queue puts are non-blocking
    (line events are dropped silently when the queue is full); the state dict
    is the authoritative source of truth.
    """
    with _downloads_lock:
        state = _download_states.get(download_id)
    if state is None:
        return
    task_queue: queue.Queue = state["queue"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        stderr_buf = _start_stderr_drain(process)
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            app.logger.debug(f"yt-dlp output: {line}")
            progress = parse_progress(line)
            with _downloads_lock:
                if progress:
                    state["progress"] = progress
                if "[Merger]" in line:
                    state["last_message"] = i18n.get("messages.merging")
                elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
                    state["last_message"] = i18n.get("messages.converting")
                elif "[download] Destination:" in line:
                    state["last_message"] = i18n.get("messages.downloading_file")
                elif (
                    "Deleting original file" in line or "Removing original file" in line
                ):
                    state["last_message"] = i18n.get("messages.cleaning_up")
            try:
                task_queue.put_nowait(("line", line))
            except queue.Full:
                pass  # state-dict snapshot already updated; line event dropped

        process.wait()
        stderr = "".join(stderr_buf)

        if process.returncode == 0:
            with _downloads_lock:
                state["status"] = "complete"
                state["last_message"] = i18n.get("download.success")
            try:
                task_queue.put_nowait(("complete", None))
            except queue.Full:
                pass  # _drain_queue will fall back to the state dict
        else:
            err_msg = i18n.get("download.error")
            err_details = ""
            if stderr:
                err_details = stderr.strip()[-500:]  # Last 500 chars of stderr
            with _downloads_lock:
                state["status"] = "error"
                state["error"] = err_msg
                if err_details:
                    state["error_details"] = err_details
            try:
                task_queue.put_nowait(("error", (err_msg, err_details)))
            except queue.Full:
                pass
    except Exception:
        app.logger.error("Download thread error", exc_info=True)
        with _downloads_lock:
            state["status"] = "error"
            state["error"] = i18n.get("messages.system_error")
        try:
            task_queue.put_nowait(("error", i18n.get("messages.system_error")))
        except queue.Full:
            pass
    finally:
        try:
            task_queue.put_nowait(("done", None))
        except queue.Full:
            pass
        _schedule_eviction(download_id)


def _line_to_sse_events(line: str) -> Generator[str, None, None]:
    """Convert a single yt-dlp output line to zero or more SSE event strings."""
    progress = parse_progress(line)
    if progress:
        yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
        if float(progress["percent"]) >= 99.9:
            msg = json.dumps({"message": i18n.get("messages.finalizing")})
            yield f"event: status\ndata: {msg}\n\n"
    if "[Merger]" in line:
        msg = json.dumps({"message": i18n.get("messages.merging")})
        yield f"event: status\ndata: {msg}\n\n"
    elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
        msg = json.dumps({"message": i18n.get("messages.converting")})
        yield f"event: status\ndata: {msg}\n\n"
    elif "[download] Destination:" in line:
        msg = json.dumps({"message": i18n.get("messages.downloading_file")})
        yield f"event: status\ndata: {msg}\n\n"
    elif "Deleting original file" in line or "Removing original file" in line:
        msg = json.dumps({"message": i18n.get("messages.cleaning_up")})
        yield f"event: status\ndata: {msg}\n\n"


def _drain_queue(
    download_id: str,
    task_queue: "queue.Queue[tuple[str, Any]]",
) -> Generator[str, None, None]:
    """Read events from a download queue and yield SSE strings until done.

    Handles client disconnect (``GeneratorExit``) gracefully: the background
    download thread is never interrupted and will run to completion regardless
    of whether any SSE client is listening.

    On each queue timeout the function also consults ``_download_states`` so
    that a reconnecting client receives the final event even when the bounded
    queue was full and the terminal event was dropped.
    """
    try:
        while True:
            try:
                event_type, payload = task_queue.get(timeout=10)
            except queue.Empty:
                # Check if the download already finished with a dropped terminal
                # event (queue was at maxsize) before sending a keepalive.
                with _downloads_lock:
                    state = _download_states.get(download_id)
                if state is not None:
                    final_status = state.get("status")
                    if final_status == "complete":
                        msg = json.dumps(
                            {
                                "message": state.get("last_message")
                                or i18n.get("download.success")
                            }
                        )
                        yield f"event: complete\ndata: {msg}\n\n"
                        break
                    elif final_status == "error":
                        err_msg = state.get("error") or i18n.get("download.error")
                        err_details = state.get("error_details", "")
                        error_data = {"error": err_msg}
                        if err_details:
                            error_data["details"] = err_details
                        yield f"event: error_event\ndata: {json.dumps(error_data)}\n\n"
                        break
                yield ": keepalive\n\n"
                continue
            if event_type == "done":
                break
            elif event_type == "complete":
                msg = json.dumps({"message": i18n.get("download.success")})
                yield f"event: complete\ndata: {msg}\n\n"
                break
            elif event_type == "error":
                payload_msg, payload_details = (
                    payload if isinstance(payload, tuple) else (payload, "")
                )
                error_data = {"error": payload_msg}
                if payload_details:
                    error_data["details"] = payload_details
                yield f"event: error_event\ndata: {json.dumps(error_data)}\n\n"
                break
            elif event_type == "line":
                yield from _line_to_sse_events(payload)
    except GeneratorExit:
        app.logger.info(
            f"Client disconnected from download {download_id}, "
            "download continues in background"
        )


@app.route("/")
def index() -> str:
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/i18n/languages")
def get_languages() -> Any:
    """Return available languages."""
    return jsonify(i18n.get_available_languages())


@app.route("/api/i18n/set-language", methods=["POST"])
def set_language() -> Any:
    """Set the current language."""
    lang = request.json.get("language", "nap") if request.json else "nap"
    i18n.set_language(lang)
    return jsonify({"current_language": i18n.current_language})


@app.route("/api/i18n/strings")
def get_i18n_strings() -> Any:
    """Return all strings for the current language for UI use."""
    return jsonify(i18n.translations.get(i18n.current_language, {}))


@app.route("/healthz")
def healthz() -> Any:
    """Lightweight liveness endpoint for frontend reconnect checks."""
    return jsonify({"status": "ok"})


@app.route("/status/<download_id>")
def download_status(download_id: str) -> Any:
    """Return the current status of a background download as JSON.

    Used by the frontend on page load to check whether an in-progress or
    recently completed download is still tracked by the server.
    """
    with _downloads_lock:
        state = _download_states.get(download_id)
        if state is None:
            return jsonify({"error": i18n.get("download.not_found")}), 404
        snapshot = {
            "status": state["status"],
            "progress": state["progress"],
            "last_message": state["last_message"],
            "error": state["error"],
            "url": state["url"],
            "metadata": state.get("metadata"),
        }
    return jsonify(snapshot)


@app.route("/metadata")
def metadata() -> Any:
    """Quick metadata lookup for a video URL.

    Returns JSON: {title, thumbnail} or an error.
    """
    video_url = (request.args.get("url") or "").strip()
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        return (
            jsonify({"error": i18n.get("download.error_invalid_url")}),
            400,
        )
    try:
        meta = fetch_metadata(video_url)
        return jsonify({"metadata": meta})
    except Exception as e:
        app.logger.debug(f"Metadata fetch error: {e}")
        return jsonify({"error": i18n.get("download.metadata_error")}), 500


@app.route("/download_stream")
def download_stream() -> Response:
    """Stream download progress using Server-Sent Events.

    **New download** – supply ``url``, ``audio_only``, ``subtitles`` query
    parameters.  The first SSE event is ``download_started`` and carries the
    opaque ``download_id`` that the client should persist (e.g. in
    ``localStorage``) for later reconnection.

    **Reconnect** – supply only ``download_id``.  The server immediately emits
    a snapshot of the last-known progress/status, then continues streaming live
    events if the download is still running.  If the download already finished
    the final ``complete`` or ``error_event`` is emitted and the stream closes.

    In both cases the actual yt-dlp subprocess runs in a background thread and
    is **never cancelled** when the browser disconnects (fire-and-forget).
    """
    reconnect_id: str | None = request.args.get("download_id")

    if reconnect_id:
        # ── Reconnect to an existing download ──────────────────────────────
        with _downloads_lock:
            state = _download_states.get(reconnect_id)
            if state is None:
                err = json.dumps({"error": i18n.get("download.not_found")})
                return Response(
                    f"event: error_event\ndata: {err}\n\n",
                    mimetype="text/event-stream",
                )
            # Take a consistent snapshot of mutable fields under the lock.
            snap = {
                "progress": state.get("progress"),
                "last_message": state.get("last_message"),
                "status": state.get("status"),
                "error": state.get("error"),
                "queue": state["queue"],
            }

        def generate_reconnect() -> Generator[str, None, None]:
            """Emit a state snapshot, then stream live events if still running."""
            if snap["progress"]:
                yield f"event: progress\ndata: {json.dumps(snap['progress'])}\n\n"
            if snap["last_message"]:
                yield f"event: status\ndata: {json.dumps({'message': snap['last_message']})}\n\n"

            if snap["status"] == "complete":
                msg = json.dumps(
                    {"message": snap["last_message"] or i18n.get("download.success")}
                )
                yield f"event: complete\ndata: {msg}\n\n"
                return
            if snap["status"] == "error":
                err_msg = snap["error"] or i18n.get("download.error")
                yield f"event: error_event\ndata: {json.dumps({'error': err_msg})}\n\n"
                return
            # Still in progress – drain the live queue
            yield from _drain_queue(reconnect_id, snap["queue"])

        return Response(
            stream_with_context(generate_reconnect()), mimetype="text/event-stream"
        )

    # ── New download ────────────────────────────────────────────────────────
    video_url: str | None = (request.args.get("url") or "").strip()
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        err = json.dumps({"error": i18n.get("download.error_invalid_url")})
        return Response(
            f"event: error_event\ndata: {err}\n\n", mimetype="text/event-stream"
        )
    audio_only: bool = request.args.get("audio_only") == "true"
    subtitles: bool = request.args.get("subtitles") == "true"
    output_dir: str = OUTPUT_DIR

    command: list[str] = [
        PYTHON_PATH,
        YTDLP_PATH,
        "--newline",
        "--no-check-certificate",
    ]

    # Use detected JS runtime and EJS scripts for YouTube challenge solving
    js_runtime_spec = _detect_js_runtime_spec()
    if js_runtime_spec:
        command.extend(["--js-runtimes", js_runtime_spec])
        command.extend(["--remote-components", "ejs:github"])

    if audio_only:
        command.extend(
            [
                "-f",
                "bestaudio/best",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
            ]
        )
    if subtitles:
        command.extend(["--write-sub", "--write-auto-sub"])

    # Add output format and URL last
    command.extend(["-o", f"{output_dir}/%(title)s.%(ext)s", video_url])

    new_id = str(uuid.uuid4())
    task_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
    # Try to fetch metadata quickly for a better UI experience. Failure
    # shouldn't block the download so we swallow errors and proceed.
    metadata_obj = None
    try:
        metadata_obj = fetch_metadata(video_url)
    except Exception:
        metadata_obj = None

    with _downloads_lock:
        _download_states[new_id] = {
            "url": video_url,
            "status": "in_progress",
            "progress": None,
            "last_message": None,
            "error": None,
            "queue": task_queue,
            "metadata": metadata_obj,
        }

    thread = threading.Thread(
        target=_run_download_thread,
        args=(new_id, command),
        daemon=True,
    )
    thread.start()

    def generate() -> Generator[str, None, None]:
        # Tell the client the download_id so it can reconnect after a disconnect
        yield f"event: download_started\ndata: {json.dumps({'download_id': new_id})}\n\n"
        yield from _drain_queue(new_id, task_queue)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/download", methods=["POST"])
def download_video() -> Any:
    from youtube_napoletano.downloader import run_yt_dlp_command

    video_url: str = (request.form.get("url") or "").strip()
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        return jsonify({"error": i18n.get("download.error_invalid_url")}), 400
    audio_only: bool = "audio_only" in request.form
    subtitles: bool = "subtitles" in request.form
    output_dir: str = OUTPUT_DIR
    format_option: str | None = "bestaudio/best" if audio_only else None
    postprocessor_args: list[str] = (
        ["-x", "--audio-format", "mp3", "--audio-quality", "0"] if audio_only else []
    )
    try:
        command: list[str] = [
            PYTHON_PATH,
            YTDLP_PATH,
            "--no-check-certificate",
            "-o",
            f"{output_dir}/%(title)s.%(ext)s",
            video_url,
        ]
        js_runtime_spec = _detect_js_runtime_spec()
        if js_runtime_spec:
            command.extend(["--js-runtimes", js_runtime_spec])
            command.extend(["--remote-components", "ejs:github"])
        if format_option:
            command.extend(["-f", format_option])
        command.extend(postprocessor_args)
        if subtitles:
            command.extend(["--write-sub", "--write-auto-sub"])
        run_yt_dlp_command(command)
        app.logger.info("Download successful")
        return jsonify({"message": i18n.get("download.success")})
    except Exception as e:
        app.logger.error(f"Download failed: {str(e)}")
        return jsonify({"error": i18n.get("download.error"), "details": str(e)}), 500


@app.route("/update", methods=["POST"])
def update() -> Any:
    """Update both yt-dlp and the app from GitHub."""
    try:
        output_lines = []

        # Step 1: Update yt-dlp if needed
        if should_update_ytdlp(UPDATE_TIMESTAMP_FILE):
            app.logger.info("Updating yt-dlp...")
            output_lines.append(i18n.get("update.updating_ytdlp"))
            try:
                update_ytdlp()
                output_lines.append(i18n.get("update.ytdlp_updated"))
            except Exception as e:
                app.logger.warning(f"yt-dlp update failed: {str(e)}")
                output_lines.append(
                    i18n.get("update.ytdlp_error").replace("{error}", str(e))
                )
        else:
            output_lines.append(i18n.get("update.ytdlp_already_updated"))

        # Step 2: Update app from GitHub using update.sh
        app.logger.info("Updating app from GitHub...")
        output_lines.append(i18n.get("update.updating_app"))

        try:
            result = subprocess.run(
                ["bash", "scripts/update.sh"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Script exit code: " + str(
                    result.returncode
                )
                app.logger.error(f"App update failed: {error_msg}")
                output_lines.append(
                    i18n.get("update.app_error").replace("{error}", error_msg)
                )
                return jsonify(
                    {
                        "message": i18n.get("update.error"),
                        "details": "\n".join(output_lines),
                    }
                ), 500

            output_lines.append(i18n.get("update.app_updated"))
            app.logger.info("App update successful")

            output = result.stdout
            full_output = "\n".join(output_lines)
            if output:
                full_output += "\n\n" + output

            return jsonify(
                {
                    "message": i18n.get("update.success"),
                    "details": full_output,
                }
            )

        except subprocess.TimeoutExpired:
            app.logger.error("Update timed out after 300 seconds")
            return jsonify(
                {
                    "message": i18n.get("update.error"),
                    "details": i18n.get("update.timeout_details"),
                }
            ), 500

    except Exception as e:
        app.logger.error(f"Update failed: {str(e)}", exc_info=True)
        return jsonify(
            {
                "message": i18n.get("update.error"),
                "details": str(e),
            }
        ), 500


# ---------------------------------------------------------------------------
# Batch (multi-URL) download
# ---------------------------------------------------------------------------


def _schedule_batch_eviction(batch_id: str) -> None:
    """Remove a finished batch from ``_batch_states`` after the TTL."""

    def _evict() -> None:
        with _batches_lock:
            _batch_states.pop(batch_id, None)
            app.logger.debug(f"Evicted batch state {batch_id}")

    timer = threading.Timer(_STATE_TTL_SECONDS, _evict)
    timer.daemon = True
    timer.start()


def _build_yt_dlp_command(
    url: str, audio_only: bool, subtitles: bool
) -> list[str]:
    """Build the yt-dlp command list for a single URL."""
    command: list[str] = [
        PYTHON_PATH,
        YTDLP_PATH,
        "--newline",
        "--no-check-certificate",
    ]

    # Use detected JS runtime and EJS scripts for YouTube challenge solving
    js_runtime_spec = _detect_js_runtime_spec()
    if js_runtime_spec:
        command.extend(["--js-runtimes", js_runtime_spec])
        command.extend(["--remote-components", "ejs:github"])

    if audio_only:
        command.extend(
            [
                "-f",
                "bestaudio/best",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
            ]
        )
    if subtitles:
        command.extend(["--write-sub", "--write-auto-sub"])

    # Add output format and URL last
    command.extend(["-o", f"{OUTPUT_DIR}/%(title)s.%(ext)s", url])
    return command


def _run_batch_thread(batch_id: str) -> None:
    """Process a batch of URLs sequentially with a delay between each one.

    Each URL is downloaded via yt-dlp in a subprocess.  Progress events are
    posted to the batch queue so an SSE client can display live updates.
    The batch continues even if individual downloads fail.
    """
    with _batches_lock:
        state = _batch_states.get(batch_id)
    if state is None:
        return
    task_queue: queue.Queue = state["queue"]
    urls = state["urls"]
    audio_only = state["audio_only"]
    subtitles = state["subtitles"]
    total = len(urls)

    for idx, url in enumerate(urls):
        with _batches_lock:
            state["current_index"] = idx
            state["items"][idx]["status"] = "downloading"
        app.logger.info(f"Batch {batch_id}: starting item {idx + 1}/{total} — {url}")
        try:
            task_queue.put_nowait(
                ("batch_item_start", {"index": idx, "url": url, "total": total})
            )
        except queue.Full:
            pass

        command = _build_yt_dlp_command(url, audio_only, subtitles)
        _last_logged_pct: int = -1
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            stderr_buf = _start_stderr_drain(process)
            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                progress = parse_progress(line)
                if progress:
                    try:
                        task_queue.put_nowait(
                            (
                                "batch_item_progress",
                                {"index": idx, "progress": progress},
                            )
                        )
                    except queue.Full:
                        pass
                    # Log progress every 25 %
                    pct = int(float(progress["percent"]))
                    if pct // 25 > _last_logged_pct // 25:
                        _last_logged_pct = pct
                        app.logger.info(
                            f"Batch {batch_id}: item {idx + 1}/{total} — "
                            f"{pct}% @ {progress['speed']} ({progress['size']})"
                        )

                # Emit status events for post-processing stages
                status_msg: str | None = None
                if "[Merger]" in line:
                    status_msg = i18n.get("messages.merging")
                elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
                    status_msg = i18n.get("messages.converting")
                elif "[download] Destination:" in line:
                    status_msg = i18n.get("messages.downloading_file")
                elif "Deleting original file" in line or "Removing original file" in line:
                    status_msg = i18n.get("messages.cleaning_up")
                if status_msg:
                    app.logger.info(
                        f"Batch {batch_id}: item {idx + 1}/{total} — {status_msg}"
                    )
                    try:
                        task_queue.put_nowait(
                            (
                                "batch_item_status",
                                {"index": idx, "message": status_msg},
                            )
                        )
                    except queue.Full:
                        pass

            process.wait()
            stderr = "".join(stderr_buf)

            if process.returncode == 0:
                app.logger.info(
                    f"Batch {batch_id}: item {idx + 1}/{total} complete — {url}"
                )
                with _batches_lock:
                    state["items"][idx]["status"] = "complete"
                try:
                    task_queue.put_nowait(
                        (
                            "batch_item_complete",
                            {"index": idx, "url": url, "total": total},
                        )
                    )
                except queue.Full:
                    pass
            else:
                err_details = stderr.strip()[-500:] if stderr else ""
                app.logger.warning(
                    f"Batch {batch_id}: item {idx + 1}/{total} failed — {url}\n{err_details}"
                )
                with _batches_lock:
                    state["items"][idx]["status"] = "error"
                    state["items"][idx]["error"] = err_details
                try:
                    task_queue.put_nowait(
                        (
                            "batch_item_error",
                            {"index": idx, "url": url, "error": err_details},
                        )
                    )
                except queue.Full:
                    pass
        except Exception as e:
            app.logger.error(f"Batch item {idx} error", exc_info=True)
            with _batches_lock:
                state["items"][idx]["status"] = "error"
                state["items"][idx]["error"] = str(e)
            try:
                task_queue.put_nowait(
                    ("batch_item_error", {"index": idx, "url": url, "error": str(e)})
                )
            except queue.Full:
                pass

        # Throttle: wait before starting the next download
        if idx < total - 1:
            try:
                task_queue.put_nowait(
                    ("batch_waiting", {"seconds": BATCH_DELAY_SECONDS})
                )
            except queue.Full:
                pass
            time.sleep(BATCH_DELAY_SECONDS)

    app.logger.info(f"Batch {batch_id}: all {total} item(s) finished")
    with _batches_lock:
        state["status"] = "complete"
    try:
        task_queue.put_nowait(("batch_complete", {"total": total}))
    except queue.Full:
        pass
    try:
        task_queue.put_nowait(("done", None))
    except queue.Full:
        pass
    _schedule_batch_eviction(batch_id)


def _drain_batch_queue(
    batch_id: str,
    task_queue: "queue.Queue[tuple[str, Any]]",
) -> Generator[str, None, None]:
    """Read events from a batch queue and yield SSE strings until done."""
    try:
        while True:
            try:
                event_type, payload = task_queue.get(timeout=10)
            except queue.Empty:
                with _batches_lock:
                    state = _batch_states.get(batch_id)
                if state is not None and state.get("status") == "complete":
                    total = len(state.get("urls", []))
                    yield f"event: batch_complete\ndata: {json.dumps({'total': total})}\n\n"
                    break
                hb_idx = state.get("current_index", 0) if state else 0
                hb_total = len(state.get("urls", [])) if state else 0
                yield f"event: batch_heartbeat\ndata: {json.dumps({'index': hb_idx, 'total': hb_total})}\n\n"
                continue
            if event_type == "done":
                break
            elif event_type == "batch_complete":
                yield f"event: batch_complete\ndata: {json.dumps(payload)}\n\n"
                break
            else:
                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    except GeneratorExit:
        app.logger.info(
            f"Client disconnected from batch {batch_id}, batch continues in background"
        )


@app.route("/batch", methods=["POST"])
def create_batch() -> Any:
    """Create a new batch download.

    Accepts JSON: {urls: [...], audio_only: bool, subtitles: bool, cookies?: str}
    Returns 202 with {batch_id, total} on success.
    """
    data = request.get_json(silent=True) or {}
    raw_urls: list[str] = data.get("urls", [])
    if not raw_urls:
        return jsonify({"error": i18n.get("batch.no_valid_urls")}), 400

    valid_urls = [
        u.strip() for u in raw_urls if u.strip() and YOUTUBE_URL_RE.match(u.strip())
    ]
    if not valid_urls:
        return jsonify({"error": i18n.get("batch.no_valid_urls")}), 400

    audio_only: bool = data.get("audio_only", False)
    subtitles: bool = data.get("subtitles", False)

    batch_id = str(uuid.uuid4())
    task_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
    with _batches_lock:
        _batch_states[batch_id] = {
            "urls": valid_urls,
            "audio_only": audio_only,
            "subtitles": subtitles,
            "status": "in_progress",
            "current_index": 0,
            "items": [
                {"url": u, "status": "pending", "error": None} for u in valid_urls
            ],
            "queue": task_queue,
        }

    thread = threading.Thread(
        target=_run_batch_thread,
        args=(batch_id,),
        daemon=True,
    )
    thread.start()

    return jsonify({"batch_id": batch_id, "total": len(valid_urls)}), 202


@app.route("/batch/status/<batch_id>")
def batch_status(batch_id: str) -> Any:
    """Return the current status of a batch download as JSON."""
    with _batches_lock:
        state = _batch_states.get(batch_id)
        if state is None:
            return jsonify({"error": i18n.get("download.not_found")}), 404
        snapshot = {
            "status": state["status"],
            "current_index": state["current_index"],
            "items": [
                {"url": item["url"], "status": item["status"], "error": item["error"]}
                for item in state["items"]
            ],
        }
    return jsonify(snapshot)


@app.route("/batch/stream/<batch_id>")
def batch_stream(batch_id: str) -> Response:
    """Stream batch download progress using Server-Sent Events.

    Reconnect-friendly: if the batch already finished the final event is
    emitted immediately.
    """
    with _batches_lock:
        state = _batch_states.get(batch_id)
        if state is None:
            err = json.dumps({"error": i18n.get("download.not_found")})
            return Response(
                f"event: error_event\ndata: {err}\n\n",
                mimetype="text/event-stream",
            )
        snap = {
            "status": state["status"],
            "items": [
                {"url": item["url"], "status": item["status"], "error": item["error"]}
                for item in state["items"]
            ],
            "queue": state["queue"],
        }

    def generate_batch() -> Generator[str, None, None]:
        # Emit a snapshot for reconnecting clients
        yield f"event: batch_snapshot\ndata: {json.dumps({'items': snap['items']})}\n\n"
        if snap["status"] == "complete":
            total = len(snap["items"])
            yield f"event: batch_complete\ndata: {json.dumps({'total': total})}\n\n"
            return
        yield from _drain_batch_queue(batch_id, snap["queue"])

    return Response(stream_with_context(generate_batch()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8443)

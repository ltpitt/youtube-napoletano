import json
import logging
import queue
import re
import subprocess
import threading
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
from youtube_napoletano.downloader import parse_progress, update_ytdlp
from youtube_napoletano.utils import should_update_ytdlp

# Flask needs to find templates and static in parent directory
template_dir = Path(__file__).parent.parent / "templates"
static_dir = Path(__file__).parent.parent / "static"

app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))

logging.basicConfig(level=logging.DEBUG)

UPDATE_TIMESTAMP_FILE = Path(config.UPDATE_TIMESTAMP_FILE)
YTDLP_PATH = config.YTDLP_PATH
PYTHON_PATH = config.PYTHON_PATH
OUTPUT_DIR = config.OUTPUT_DIR
YOUTUBE_URL_RE = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$")

# Active download states: download_id -> state dict.
# Kept in memory for the lifetime of the server process so that the GUI can
# reconnect after a browser close / app switch and see the current status.
_download_states: dict[str, dict] = {}
_downloads_lock = threading.Lock()


def _run_download_thread(download_id: str, command: list[str]) -> None:
    """Run yt-dlp in a background thread, posting events to a queue.

    The download continues even if the SSE client disconnects (fire-and-forget).
    Progress and status are also stored in ``_download_states`` so that the GUI
    can poll or reconnect at any time and get an up-to-date snapshot.
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
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            app.logger.debug(f"yt-dlp output: {line}")
            progress = parse_progress(line)
            if progress:
                state["progress"] = progress
            if "[Merger]" in line:
                state["last_message"] = "Sto azzeccanno 'e piezze..."
            elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
                state["last_message"] = "Sto cunvertenno..."
            elif "[download] Destination:" in line:
                state["last_message"] = "Sto scarricanno..."
            elif "Deleting original file" in line or "Removing original file" in line:
                state["last_message"] = "Sto pulizianno..."
            task_queue.put(("line", line))
        process.wait()
        if process.returncode == 0:
            state["status"] = "complete"
            state["last_message"] = "'O scarricamento è fernuto!"
            task_queue.put(("complete", None))
        else:
            state["status"] = "error"
            state["error"] = "'O scarricamento s'è arricettato"
            task_queue.put(("error", "'O scarricamento s'è arricettato"))
    except Exception as e:
        app.logger.error(f"Download thread error: {str(e)}")
        state["status"] = "error"
        state["error"] = str(e)
        task_queue.put(("error", str(e)))
    finally:
        task_queue.put(("done", None))


def _line_to_sse_events(line: str) -> Generator[str, None, None]:
    """Convert a single yt-dlp output line to zero or more SSE event strings."""
    progress = parse_progress(line)
    if progress:
        yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
        if float(progress["percent"]) >= 99.9:
            msg = json.dumps({"message": "Scarricamento cumpletato, sto pulizianno..."})
            yield f"event: status\ndata: {msg}\n\n"
    if "[Merger]" in line:
        msg = json.dumps({"message": "Sto azzeccanno 'e piezze..."})
        yield f"event: status\ndata: {msg}\n\n"
    elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
        msg = json.dumps({"message": "Sto cunvertenno..."})
        yield f"event: status\ndata: {msg}\n\n"
    elif "[download] Destination:" in line:
        msg = json.dumps({"message": "Sto scarricanno..."})
        yield f"event: status\ndata: {msg}\n\n"
    elif "Deleting original file" in line or "Removing original file" in line:
        msg = json.dumps({"message": "Sto pulizianno..."})
        yield f"event: status\ndata: {msg}\n\n"


def _drain_queue(
    download_id: str,
    task_queue: "queue.Queue[tuple[str, Any]]",
) -> Generator[str, None, None]:
    """Read events from a download queue and yield SSE strings until done.

    Handles client disconnect (``GeneratorExit``) gracefully: the background
    download thread is never interrupted and will run to completion regardless
    of whether any SSE client is listening.
    """
    try:
        while True:
            try:
                event_type, payload = task_queue.get(timeout=30)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            if event_type == "done":
                break
            elif event_type == "complete":
                msg = json.dumps({"message": "'O scarricamento è fernuto!"})
                yield f"event: complete\ndata: {msg}\n\n"
                break
            elif event_type == "error":
                err = json.dumps({"error": payload})
                yield f"event: error_event\ndata: {err}\n\n"
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


@app.route("/status/<download_id>")
def download_status(download_id: str) -> Any:
    """Return the current status of a background download as JSON.

    Used by the frontend on page load to check whether an in-progress or
    recently completed download is still tracked by the server.
    """
    with _downloads_lock:
        state = _download_states.get(download_id)
    if state is None:
        return jsonify({"error": "Download non trovato"}), 404
    return jsonify(
        {
            "status": state["status"],
            "progress": state["progress"],
            "last_message": state["last_message"],
            "error": state["error"],
            "url": state["url"],
        }
    )


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
            err = json.dumps({"error": "Download non trovato"})
            return Response(
                f"event: error_event\ndata: {err}\n\n",
                mimetype="text/event-stream",
            )

        def generate_reconnect() -> Generator[str, None, None]:
            """Emit a state snapshot, then stream live events if still running."""
            snap_progress = state.get("progress")
            snap_message = state.get("last_message")
            snap_status = state.get("status")

            if snap_progress:
                yield f"event: progress\ndata: {json.dumps(snap_progress)}\n\n"
            if snap_message:
                yield f"event: status\ndata: {json.dumps({'message': snap_message})}\n\n"

            if snap_status == "complete":
                msg = json.dumps(
                    {"message": snap_message or "'O scarricamento è fernuto!"}
                )
                yield f"event: complete\ndata: {msg}\n\n"
                return
            if snap_status == "error":
                err_msg = state.get("error") or "'O scarricamento s'è arricettato"
                yield f"event: error_event\ndata: {json.dumps({'error': err_msg})}\n\n"
                return
            # Still in progress – drain the live queue
            yield from _drain_queue(reconnect_id, state["queue"])

        return Response(
            stream_with_context(generate_reconnect()), mimetype="text/event-stream"
        )

    # ── New download ────────────────────────────────────────────────────────
    video_url: str = request.args.get("url")
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        err = json.dumps({"error": "URL nun valida. Miette nu link YouTube buono!"})
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
        "-o",
        f"{output_dir}/%(title)s.%(ext)s",
        video_url,
    ]
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

    new_id = str(uuid.uuid4())
    task_queue: queue.Queue = queue.Queue()
    with _downloads_lock:
        _download_states[new_id] = {
            "url": video_url,
            "status": "in_progress",
            "progress": None,
            "last_message": None,
            "error": None,
            "queue": task_queue,
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

    video_url: str = request.form["url"]
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        return jsonify({"error": "URL nun valida. Miette nu link YouTube buono!"}), 400
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
            "-o",
            f"{output_dir}/%(title)s.%(ext)s",
            video_url,
        ]
        if format_option:
            command.extend(["-f", format_option])
        command.extend(postprocessor_args)
        if subtitles:
            command.extend(["--write-sub", "--write-auto-sub"])
        run_yt_dlp_command(command)
        app.logger.info("Download successful")
        return jsonify({"message": "'O scarricamento è fernuto!"})
    except Exception as e:
        app.logger.error(f"Download failed: {str(e)}")
        return jsonify(
            {"error": "'O scarricamento s'è arricettato", "details": str(e)}
        ), 500


@app.route("/update", methods=["POST"])
def update() -> Any:
    if not should_update_ytdlp(UPDATE_TIMESTAMP_FILE):
        return jsonify({"message": "yt-dlp is already up to date."})
    try:
        update_ytdlp()
        return jsonify({"message": "yt-dlp aggiurnato cu successo!"})
    except Exception as e:
        app.logger.error(f"yt-dlp update failed: {str(e)}")
        return jsonify({"error": "Errore curiouso dint' all'aggiurnamiento"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8443)

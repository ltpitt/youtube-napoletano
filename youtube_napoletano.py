import json
import logging
import re
from typing import Any
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)
from pathlib import Path
from datetime import datetime
import config
from downloader import parse_progress, update_ytdlp
from utils import should_update_ytdlp

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

UPDATE_TIMESTAMP_FILE = Path(config.UPDATE_TIMESTAMP_FILE)
YTDLP_PATH = config.YTDLP_PATH
PYTHON_PATH = config.PYTHON_PATH
OUTPUT_DIR = config.OUTPUT_DIR
YOUTUBE_URL_RE = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$")

@app.route("/")
def index() -> str:
    return render_template("index.html")

@app.route("/download_stream")
def download_stream() -> Response:
    """Stream download progress using Server-Sent Events"""
    from downloader import parse_progress
    import subprocess
    video_url: str = request.args.get("url")
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        err = json.dumps({"error": "URL nun valida. Miette nu link YouTube buono!"})
        return Response(f"event: error_event\ndata: {err}\n\n", mimetype="text/event-stream")
    audio_only: bool = request.args.get("audio_only") == "true"
    output_dir: str = OUTPUT_DIR

    def generate() -> Generator[str, None, None]:
        try:
            command: list[str] = [
                PYTHON_PATH,
                YTDLP_PATH,
                "--newline",
                "-o",
                f"{output_dir}/%(title)s.%(ext)s",
                video_url,
            ]
            if audio_only:
                command.extend([
                    "-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"
                ])
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                line = line.strip()
                app.logger.debug(f"yt-dlp output: {line}")
                progress = parse_progress(line)
                if progress:
                    data = json.dumps(progress)
                    yield f"event: progress\ndata: {data}\n\n"
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
                elif ("Deleting original file" in line or "Removing original file" in line):
                    msg = json.dumps({"message": "Sto pulizianno..."})
                    yield f"event: status\ndata: {msg}\n\n"
            process.wait()
            if process.returncode == 0:
                msg = json.dumps({"message": "'O scarricamento è fernuto!"})
                yield f"event: complete\ndata: {msg}\n\n"
            else:
                err = json.dumps({"error": "'O scarricamento s'è arricettato"})
                yield f"event: error_event\ndata: {err}\n\n"
        except Exception as e:
            app.logger.error(f"Download stream error: {str(e)}")
            err = json.dumps({"error": str(e)})
            yield f"event: error_event\ndata: {err}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/download", methods=["POST"])
def download_video() -> Any:
    from downloader import run_yt_dlp_command
    video_url: str = request.form["url"]
    if not video_url or not YOUTUBE_URL_RE.match(video_url):
        return jsonify({"error": "URL nun valida. Miette nu link YouTube buono!"}), 400
    audio_only: bool = "audio_only" in request.form
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
            command.insert(1, "-f")
            command.insert(2, format_option)
        command.extend(postprocessor_args)
        run_yt_dlp_command(command)
        app.logger.info("Download successful")
        return jsonify({"message": "'O scarricamento è fernuto!"})
    except Exception as e:
        app.logger.error(f"Download failed: {str(e)}")
        return jsonify({"error": "'O scarricamento s'è arricettato", "details": str(e)}), 500

@app.route("/update", methods=["POST"])
def update() -> Any:
    from downloader import update_ytdlp
    from utils import should_update_ytdlp
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

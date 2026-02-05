import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, stream_with_context


app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Path to timestamp file for update tracking
UPDATE_TIMESTAMP_FILE = Path('/tmp/yt-dlp-last-update.txt')
YTDLP_PATH = '/var/services/homes/pitto/.local/bin/yt-dlp'
PYTHON_PATH = '/var/services/homes/pitto/scripts/youtube_napoletano/.venv/bin/python3.12'


def should_update_ytdlp():
    """Check if yt-dlp should be updated (once per day)"""
    if not UPDATE_TIMESTAMP_FILE.exists():
        return True

    try:
        last_update = datetime.fromisoformat(UPDATE_TIMESTAMP_FILE.read_text().strip())
        return datetime.now() - last_update > timedelta(days=1)
    except Exception:
        return True


def update_ytdlp():
    """Update yt-dlp if needed, non-blocking"""
    if not should_update_ytdlp():
        return

    try:
        subprocess.run(
            [PYTHON_PATH, YTDLP_PATH, '-U'],
            capture_output=True,
            timeout=30,
            check=False  # Don't fail if update fails
        )
        UPDATE_TIMESTAMP_FILE.write_text(datetime.now().isoformat())
        app.logger.info('yt-dlp updated successfully')
    except Exception as e:
        app.logger.warning(f'yt-dlp update failed (continuing anyway): {e}')


def parse_progress(line):
    """Parse yt-dlp output to extract progress information"""
    # Match pattern like: [download] 100.0% of   10.17MiB at    6.05MiB/s ETA 00:00
    match = re.search(
        r'\[download\]\s+(\d+\.?\d*)%\s+of\s+(\d+\.?\d*\w+iB)\s+at\s+(\d+\.?\d*\w+iB/s)\s+ETA\s+(\d+:\d+)',
        line
    )
    if match:
        return {
            'percent': match.group(1),
            'size': match.group(2),
            'speed': match.group(3),
            'eta': match.group(4)
        }
    
    # Fallback pattern when speed is not available (early in download)
    match_simple = re.search(r'\[download\]\s+(\d+\.?\d*)%\s+of\s+(\d+\.?\d*\w+iB)', line)
    if match_simple:
        return {
            'percent': match_simple.group(1),
            'size': match_simple.group(2),
            'speed': 'N/A',
            'eta': 'N/A'
        }
    
    return None


@app.route('/')
def index():
    return render_template_string('''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>'O Tubb</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background: url('/static/naples-background.jpg') no-repeat center center fixed;
            background-size: cover;
            color: #fff;
            text-align: center;
            padding-top: 50px;
        }
        .container {
            width: 90%;
            margin: auto;
            background: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 10px;
        }
        input[type="text"] {
            width: 95%;
            padding: 10px;
            margin-bottom: 20px;
            border: none;
            border-radius: 5px;
        }
        input[type="checkbox"] {
            margin-bottom: 20px;
        }
        button {
            padding: 10px 20px;
            background-image: linear-gradient(to right, #0054a6, #0054a6);
            color: #fff;
            border: 2px solid #0082ca;
            border-radius: 5px;
            cursor: pointer;
            font-family: 'Lucida Console', 'Courier New', monospace;
            text-shadow: 1px 1px 2px #0005;
            box-shadow: 3px 3px 5px #0003;
            transition: transform 0.3s ease;
        }
        button:hover {
            transform: translateY(-3px);
            box-shadow: 3px 6px 5px #0003;
        }
        .message {
            margin-top: 20px;
            padding: 10px;
            border-radius: 5px;
            font-size: 1.2em;
        }
        .success {
            background-color: #4CAF50;
            color: white;
        }
        .error {
            background-color: #f44336;
            color: white;
        }
        .progress-container {
            display: none;
            margin-top: 20px;
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
        }
        .progress-bar-bg {
            width: 100%;
            height: 30px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .progress-bar {
            height: 100%;
            background: linear-gradient(to right, #0054a6, #0082ca);
            width: 0%;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            text-shadow: 1px 1px 2px #000;
        }
        .progress-info {
            font-size: 0.9em;
            color: #fff;
            text-align: left;
        }
        .progress-bar.indeterminate {
            width: 100% !important;
            background: linear-gradient(90deg, #0054a6, #0082ca, #0054a6);
            background-size: 200% 100%;
            animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .footer {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            text-align: center;
        }
        .footer a {
            color: rgba(255, 255, 255, 0.5);
            text-decoration: none;
            font-size: 0.85em;
            transition: color 0.3s ease;
        }
        .footer a:hover {
            color: rgba(255, 255, 255, 0.8);
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube Napulitano</h1>
        <form id="downloadForm">
            <input type="text" name="url" placeholder="Miette ccà 'o link d’’o video 'e YouTube" required>
            <div>
                <label>
                    <input type="checkbox" name="audio_only"> Sulo audio
                </label>
            </div>
            <button type="submit">Scarrica</button>
        </form>
        <div id="progressContainer" class="progress-container">
            <div class="progress-bar-bg">
                <div id="progressBar" class="progress-bar">0%</div>
            </div>
            <div id="progressInfo" class="progress-info"></div>
        </div>
        <div id="messageBox"></div>
        <div class="footer">
            <a href="#" id="updateLink">⚙️ Aggiorna yt-dlp</a>
        </div>
    </div>
    <script>
        document.getElementById('downloadForm').onsubmit = function(event) {
            event.preventDefault();
            var messageBox = document.getElementById('messageBox');
            var progressContainer = document.getElementById('progressContainer');
            var progressBar = document.getElementById('progressBar');
            var progressInfo = document.getElementById('progressInfo');

            messageBox.innerHTML = '';
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            progressInfo.innerHTML = "Sto accumincianno...";
            
            var formData = new FormData(this);
            var url = formData.get('url');
            var audioOnly = formData.get('audio_only') ? 'true' : 'false';
            
            var eventSource = new EventSource('/download_stream?url=' + encodeURIComponent(url) + '&audio_only=' + audioOnly);
            
            eventSource.addEventListener('progress', function(e) {
                var data = JSON.parse(e.data);
                progressBar.style.width = data.percent + '%';
                progressBar.textContent = data.percent + '%';
                progressInfo.innerHTML = 'Velocità: ' + data.speed + ' | Dimensione: ' + data.size;
            });
            
            eventSource.addEventListener('status', function(e) {
                var data = JSON.parse(e.data);
                progressInfo.innerHTML = data.message;
            });
            
            eventSource.addEventListener('complete', function(e) {
                var data = JSON.parse(e.data);
                eventSource.close();
                progressContainer.style.display = 'none';
                
                var messageElement = document.createElement('div');
                messageElement.className = 'message success';
                messageElement.textContent = data.message;
                messageBox.appendChild(messageElement);
            });
            
            eventSource.addEventListener('error_event', function(e) {
                var data = JSON.parse(e.data);
                eventSource.close();
                progressContainer.style.display = 'none';
                
                var messageElement = document.createElement('div');
                messageElement.className = 'message error';
                messageElement.textContent = data.error;
                messageBox.appendChild(messageElement);
            });
            
            eventSource.onerror = function() {
                eventSource.close();
                progressContainer.style.display = 'none';
                
                var messageElement = document.createElement('div');
                messageElement.className = 'message error';
                messageElement.textContent = "Errore 'e connessione";
                messageBox.appendChild(messageElement);
            };
        };

        document.getElementById('updateLink').onclick = function(e) {
            e.preventDefault();
            var messageBox = document.getElementById('messageBox');
            var progressContainer = document.getElementById('progressContainer');
            var progressBar = document.getElementById('progressBar');
            var progressInfo = document.getElementById('progressInfo');
            
            messageBox.innerHTML = '';
            progressContainer.style.display = 'block';
            progressBar.className = 'progress-bar indeterminate';
            progressBar.textContent = '';
            progressInfo.innerHTML = "Sto aggiurnanno yt-dlp...";

            fetch('/update', {
                method: 'POST'
            }).then(function(response) {
                return response.json();
            }).then(function(data) {
                progressContainer.style.display = 'none';
                progressBar.className = 'progress-bar';
                
                var message = data.message || data.error;
                var messageElement = document.createElement('div');
                messageElement.className = 'message ' + (data.message ? 'success' : 'error');
                messageElement.textContent = message;
                messageBox.appendChild(messageElement);
            }).catch(function(error) {
                progressContainer.style.display = 'none';
                progressBar.className = 'progress-bar';
                
                var messageElement = document.createElement('div');
                messageElement.className = 'message error';
                messageElement.textContent = 'Error: ' + error.message;
                messageBox.appendChild(messageElement);
            });
        };
    </script>
</body>
</html>
    ''')


@app.route('/download_stream')
def download_stream():
    """Stream download progress using Server-Sent Events"""
    video_url = request.args.get('url')
    audio_only = request.args.get('audio_only') == 'true'
    output_dir = '/volume1/video/Youtube-Napoletano'

    def generate():
        try:
            command = [PYTHON_PATH, YTDLP_PATH, '--newline', '-o', f'{output_dir}/%(title)s.%(ext)s', video_url]

            if audio_only:
                command.extend(['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', '0'])

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                if not line:
                    break

                line = line.strip()
                app.logger.debug(f'yt-dlp output: {line}')

                # Parse progress
                progress = parse_progress(line)
                if progress:
                    data = json.dumps(progress)
                    yield f"event: progress\ndata: {data}\n\n"
                    
                    # When we hit 100%, notify that post-processing may follow
                    if float(progress['percent']) >= 99.9:
                        msg = json.dumps({'message': 'Scarricamento cumpletato, sto pulizianno...'})
                        yield f"event: status\ndata: {msg}\n\n"

                # Check for post-processing status (universal patterns)
                if '[Merger]' in line:
                    msg = json.dumps({'message': 'Sto azzeccanno \'e piezze...'})
                    yield f"event: status\ndata: {msg}\n\n"
                elif '[ExtractAudio]' in line or '[ffmpeg]' in line:
                    msg = json.dumps({'message': 'Sto cunvertenno...'})
                    yield f"event: status\ndata: {msg}\n\n"
                elif '[download] Destination:' in line:
                    msg = json.dumps({'message': 'Sto scarricanno...'})
                    yield f"event: status\ndata: {msg}\n\n"
                elif 'Deleting original file' in line or 'Removing original file' in line:
                    msg = json.dumps({'message': 'Sto pulizianno...'})
                    yield f"event: status\ndata: {msg}\n\n"

            process.wait()

            if process.returncode == 0:
                msg = json.dumps({'message': "'O scarricamento è fernuto!"})
                yield f"event: complete\ndata: {msg}\n\n"
            else:
                err = json.dumps({'error': "'O scarricamento s'è arricettato"})
                yield f"event: error_event\ndata: {err}\n\n"

        except Exception as e:
            app.logger.error(f'Download stream error: {str(e)}')
            err = json.dumps({'error': str(e)})
            yield f"event: error_event\ndata: {err}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/download', methods=['POST'])
def download_video():
    video_url = request.form['url']
    audio_only = 'audio_only' in request.form
    output_dir = '/volume1/video/Youtube-Napoletano'
    format_option = 'bestaudio/best' if audio_only else None
    postprocessor_args = ['-x', '--audio-format', 'mp3', '--audio-quality', '0'] if audio_only else []

    try:
        command = [PYTHON_PATH, YTDLP_PATH, '-o', f'{output_dir}/%(title)s.%(ext)s', video_url]
        if format_option:
            command.insert(1, '-f')
            command.insert(2, format_option)
        command.extend(postprocessor_args)

        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        app.logger.info('Download successful')
        return jsonify({'message': "'O scarricamento è fernuto!"})
    except subprocess.CalledProcessError as e:
        app.logger.error(f'Download failed: {e.stderr}')
        return jsonify({'error': "'O scarricamento s'è arricettato", 'details': e.stderr}), 500


@app.route('/update', methods=['POST'])
def update():
    """Manual yt-dlp update endpoint"""
    try:
        subprocess.run(
            [PYTHON_PATH, YTDLP_PATH, '-U'],
            capture_output=True,
            text=True,
            timeout=60,
            check=True
        )
        app.logger.info('yt-dlp update successful')
        # Update timestamp file
        UPDATE_TIMESTAMP_FILE.write_text(datetime.now().isoformat())
        return jsonify({'message': 'yt-dlp aggiurnato cu successo!'})
    except subprocess.TimeoutExpired:
        app.logger.error('yt-dlp update timed out')
        return jsonify({'error': "'O tiempo è fernuto (timeout)"}), 500
    except subprocess.CalledProcessError as e:
        app.logger.error(f'yt-dlp update failed: {e.stderr}')
        return jsonify({'error': "'O aggiurnamiento s'è arricettato", 'details': e.stderr}), 500
    except Exception as e:
        app.logger.error(f'Unexpected error during update: {str(e)}')
        return jsonify({'error': "Errore curiouso dint' all'aggiurnamiento"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8443)

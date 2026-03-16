var DOWNLOAD_ID_KEY = 'yt_napoletano_download_id';

function storeDownloadId(id) {
    localStorage.setItem(DOWNLOAD_ID_KEY, id);
}

function clearDownloadId() {
    localStorage.removeItem(DOWNLOAD_ID_KEY);
}

function getStoredDownloadId() {
    return localStorage.getItem(DOWNLOAD_ID_KEY);
}

function showMessage(text, type) {
    var messageBox = document.getElementById('messageBox');
    var messageElement = document.createElement('div');
    messageElement.className = 'message ' + type;
    messageElement.textContent = text;
    messageBox.appendChild(messageElement);
}

/**
 * Open an SSE connection to the given URL and wire up all event handlers.
 * Used for both new downloads and reconnects.
 */
function connectToDownloadStream(eventSourceUrl, initialMessage) {
    var messageBox = document.getElementById('messageBox');
    var progressContainer = document.getElementById('progressContainer');
    var progressBar = document.getElementById('progressBar');
    var progressInfo = document.getElementById('progressInfo');

    messageBox.innerHTML = '';
    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressInfo.innerHTML = initialMessage || "Sto accumincianno...";

    var downloadFinished = false;
    var eventSource = new EventSource(eventSourceUrl);

    eventSource.addEventListener('download_started', function(e) {
        var data = JSON.parse(e.data);
        storeDownloadId(data.download_id);
    });

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
        downloadFinished = true;
        var data = JSON.parse(e.data);
        eventSource.close();
        progressContainer.style.display = 'none';
        clearDownloadId();
        showMessage(data.message, 'success');
    });

    eventSource.addEventListener('error_event', function(e) {
        downloadFinished = true;
        var data = JSON.parse(e.data);
        eventSource.close();
        progressContainer.style.display = 'none';
        clearDownloadId();
        showMessage(data.error, 'error');
    });

    eventSource.onerror = function() {
        if (downloadFinished) { return; }
        eventSource.close();
        progressContainer.style.display = 'none';
        // The download is still running on the server. Inform the user so they
        // know they can reload the page to check the result.
        showMessage("Connessione persa – 'o scarricamento va avanti. Apri 'a pagina d''a capo p' vedé 'o risultato.", 'error');
    };
}

document.getElementById('downloadForm').onsubmit = function(event) {
    event.preventDefault();
    var formData = new FormData(this);
    var url = formData.get('url');
    var audioOnly = formData.get('audio_only') ? 'true' : 'false';
    var subtitles = formData.get('subtitles') ? 'true' : 'false';

    connectToDownloadStream(
        '/download_stream?url=' + encodeURIComponent(url) +
        '&audio_only=' + audioOnly +
        '&subtitles=' + subtitles
    );
};

// On page load: check whether a previous download is still tracked by the
// server so the user can see its status after reopening the browser.
window.addEventListener('DOMContentLoaded', function() {
    var downloadId = getStoredDownloadId();
    if (!downloadId) { return; }

    fetch('/status/' + downloadId)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.error) {
                // Server was restarted or id is unknown – clean up silently.
                clearDownloadId();
                return;
            }
            if (data.status === 'complete') {
                clearDownloadId();
                showMessage(data.last_message || "'O scarricamento è fernuto!", 'success');
            } else if (data.status === 'error') {
                clearDownloadId();
                showMessage(data.error || "'O scarricamento s'è arricettato", 'error');
            } else {
                // Still in progress – reconnect to the live SSE stream.
                connectToDownloadStream(
                    '/download_stream?download_id=' + downloadId,
                    "Recuperanno 'o scarricamento 'e prima..."
                );
            }
        })
        .catch(function() {
            // Server unreachable – leave the id stored and try again on next load.
        });
});

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

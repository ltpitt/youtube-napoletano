var DOWNLOAD_ID_KEY = 'yt_napoletano_download_id';

function storeDownloadId(id) { localStorage.setItem(DOWNLOAD_ID_KEY, id); }
function clearDownloadId()   { localStorage.removeItem(DOWNLOAD_ID_KEY); }
function getStoredDownloadId() { return localStorage.getItem(DOWNLOAD_ID_KEY); }

/* ── Top-bar loader (slim line at top of card) ───────────────────────── */
function topbarStart() {
    document.getElementById('topbar').className = 'topbar loading';
}
function topbarDone() {
    var bar = document.getElementById('topbar');
    bar.className = 'topbar done';
    setTimeout(function() { bar.className = 'topbar'; }, 600);
}

/* ── Notification messages ───────────────────────────────────────────── */
function extractErrorTitle(fullText) {
    // Extract first meaningful line or first 100 chars
    var lines = fullText.split('\n');
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.length > 0 && !line.startsWith('[')) {
            return line.substring(0, 120);
        }
    }
    return fullText.substring(0, 120);
}

function showMessage(text, type, details) {
    var messageBox = document.getElementById('messageBox');
    var el = document.createElement('div');
    el.className = 'message ' + type;
    var icon = type === 'success' ? '✓' : '⚠️';
    var hasDetails = details && details.trim().length > 0;
    
    // For error messages with details, extract a cleaner title
    var displayTitle = text;
    if (type === 'error' && hasDetails) {
        var extracted = extractErrorTitle(details);
        if (extracted.length > 0 && extracted !== details) {
            displayTitle = extracted;
        }
    }
    
    var headerHtml = '<div class="message-icon">' + icon + '</div>' +
                     '<div class="message-main">' +
                     '  <div class="message-title">' + escapeHtml(displayTitle) + '</div>' +
                     (hasDetails ? '  <div class="message-hint">Puoza p\' vedé \'e dettagli</div>' : '') +
                     '</div>' +
                     '<button class="message-close" onclick="event.stopPropagation(); this.parentElement.remove()" aria-label="Chiozze">×</button>';
    el.innerHTML = headerHtml;
    
    if (hasDetails) {
        var detailsEl = document.createElement('div');
        detailsEl.className = 'message-details';
        detailsEl.innerHTML = '<pre class="message-trace">' + escapeHtml(details) + '</pre>' +
                             '<button class="message-copy" onclick="event.stopPropagation(); copyToClipboard(this)">📋 Copia \'e dettagli</button>';
        el.appendChild(detailsEl);
        el.onclick = function(e) {
            if (e.target.closest('.message-close') || e.target.closest('.message-copy')) return;
            el.classList.toggle('expanded');
        };
    }
    messageBox.appendChild(el);
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyToClipboard(btn) {
    var details = btn.parentElement.querySelector('pre').textContent;
    navigator.clipboard.writeText(details).then(function() {
        var orig = btn.textContent;
        btn.textContent = '✓ Copiato';
        setTimeout(function() { btn.textContent = orig; }, 2000);
    });
}

/* ── Extract YouTube video ID from URL ────────────────────────────────── */
function extractYouTubeId(url) {
    var match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return match ? match[1] : null;
}

/* ── Metadata card ───────────────────────────────────────────────────── */
function renderMetadata(meta, originalUrl) {
    var card = document.getElementById('metaCard');
    topbarDone();
    if (!meta || !originalUrl) { card.style.display = 'none'; return; }
    
    // Extract YouTube video ID and embed
    var videoId = extractYouTubeId(originalUrl);
    var videoFrame = document.getElementById('videoFrame');
    
    if (videoId) {
        videoFrame.src = 'https://www.youtube.com/embed/' + videoId + '?rel=0';
        card.style.display = 'flex';
    } else {
        card.style.display = 'none';
        showMessage('Nun riesco a truvà \'o video. Verifica che \'o link sia corretta!', 'error');
    }
}

/* ── Progress container helpers ──────────────────────────────────────── */
function showProgress(headerHtml) {
    var c  = document.getElementById('progressContainer');
    var pb = document.getElementById('progressBar');
    var ph = c.querySelector('.progress-header');
    c.style.display = 'block';
    pb.className = 'progress-bar';
    pb.style.width = '0%';
    ph.innerHTML = headerHtml;
    document.getElementById('progressInfo').textContent = '';
}
function showProgressIndeterminate(headerHtml) {
    var c  = document.getElementById('progressContainer');
    var pb = document.getElementById('progressBar');
    var ph = c.querySelector('.progress-header');
    c.style.display = 'block';
    pb.className = 'progress-bar indeterminate';
    ph.innerHTML = headerHtml;
    document.getElementById('progressInfo').textContent = '';
}
function hideProgress() {
    document.getElementById('progressContainer').style.display = 'none';
    document.getElementById('progressBar').className = 'progress-bar';
}

/* ── SSE download stream ─────────────────────────────────────────────── */
function connectToDownloadStream(eventSourceUrl, initialMessage) {
    var messageBox   = document.getElementById('messageBox');
    var progressBar  = document.getElementById('progressBar');
    var progressInfo = document.getElementById('progressInfo');
    
    // Extract video URL from query string if present
    var videoUrl = null;
    var urlMatch = eventSourceUrl.match(/[?&]url=([^&]+)/);
    if (urlMatch) {
        videoUrl = decodeURIComponent(urlMatch[1]);
    }

    messageBox.innerHTML = '';
    topbarStart();
    showProgress('<span class="progress-icon">⬇️</span><span>' + (initialMessage || "Sto accumincianno...") + '</span>');

    var downloadFinished = false;
    var eventSource = new EventSource(eventSourceUrl);

    eventSource.addEventListener('download_started', function(e) {
        topbarDone();
        storeDownloadId(JSON.parse(e.data).download_id);
    });

    eventSource.addEventListener('status', function(e) {
        var data = JSON.parse(e.data);
        if (data.metadata) { renderMetadata(data.metadata, videoUrl || data.url); }
        if (data.message)  { progressInfo.textContent = data.message; }
    });

    eventSource.addEventListener('progress', function(e) {
        var data = JSON.parse(e.data);
        progressBar.style.width = data.percent + '%';
        progressInfo.textContent = data.percent + '% • Velocità: ' + data.speed + ' • Dimensione: ' + data.size;
    });

    eventSource.addEventListener('complete', function(e) {
        downloadFinished = true;
        eventSource.close();
        hideProgress();
        clearDownloadId();
        showMessage(JSON.parse(e.data).message || "'O scarricamento è fernuto!", 'success');
    });

    eventSource.addEventListener('error_event', function(e) {
        downloadFinished = true;
        eventSource.close();
        hideProgress();
        clearDownloadId();
        var data = JSON.parse(e.data);
        var errorMsg = data.error || 'Errore sconosciuto, scusa!';
        var details = data.details || '';
        showMessage(errorMsg, 'error', details);
    });

    eventSource.onerror = function() {
        if (downloadFinished) { return; }
        eventSource.close();
        hideProgress();
        showMessage("Connessione persa \u2013 'o scarricamento va avanti. Apri 'a pagina d''a capo p' ved\u00e9 'o risultato.", 'error');
    };
}

/* ── Form submit ─────────────────────────────────────────────────────── */
document.getElementById('downloadForm').onsubmit = function(event) {
    event.preventDefault();
    var fd = new FormData(this);
    connectToDownloadStream(
        '/download_stream?url=' + encodeURIComponent(fd.get('url')) +
        '&audio_only=' + (fd.get('audio_only') ? 'true' : 'false') +
        '&subtitles=' + (fd.get('subtitles') ? 'true' : 'false')
    );
};

/* ── Resume on page load ─────────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', function() {
    var id = getStoredDownloadId();
    if (!id) { return; }
    topbarStart();
    fetch('/status/' + id)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            topbarDone();
            if (data.error) { clearDownloadId(); return; }
            if (data.status === 'complete') {
                clearDownloadId();
                showMessage(data.last_message || "'O scarricamento è fernuto!", 'success');
            } else if (data.status === 'error') {
                clearDownloadId();
                showMessage(data.error || "'O scarricamento s'è arricettato", 'error');
            } else {
                if (data.metadata) { renderMetadata(data.metadata, data.url); }
                connectToDownloadStream(
                    '/download_stream?download_id=' + id,
                    "Recuperanno 'o scarricamento 'e prima..."
                );
            }
        })
        .catch(function() { topbarDone(); });
});

/* ── Update yt-dlp and app ──────────────────────────────────────────── */
document.getElementById('updateLink').onclick = function(e) {
    e.preventDefault();
    document.getElementById('messageBox').innerHTML = '';
    topbarStart();
    showProgressIndeterminate('<span class="progress-icon">🔄</span><span>Sto aggiurnanno...</span>');

    fetch('/update', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            topbarDone();
            hideProgress();
            var details = data.details ? '[' + new Date().toISOString() + ']\n' + data.details : '';
            showMessage(data.message || data.error, data.message ? 'success' : 'error', details);
        })
        .catch(function(err) {
            topbarDone();
            hideProgress();
            var details = '[' + new Date().toISOString() + ']\n' + err.message;
            showMessage('Errore \'e rete', 'error', details);
        });
};
/* ── Theme toggle ──────────────────────────────────────────────────── */
(function() {
    var themeCheckbox = document.getElementById('themeCheckbox');
    var savedTheme = localStorage.getItem('theme') || 'dark';
    
    function applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-mode');
            themeCheckbox.checked = true;
        } else {
            document.body.classList.remove('light-mode');
            themeCheckbox.checked = false;
        }
        localStorage.setItem('theme', theme);
    }
    
    // Apply saved theme on load
    applyTheme(savedTheme);
    
    // Toggle theme on checkbox change
    themeCheckbox.addEventListener('change', function() {
        applyTheme(this.checked ? 'light' : 'dark');
    });
})();

/* ── Download preferences (audio_only, subtitles) ────────────────── */
(function() {
    var audioCheckbox = document.querySelector('input[name="audio_only"]');
    var subtitlesCheckbox = document.querySelector('input[name="subtitles"]');
    
    // Load saved preferences on page load
    var savedAudioOnly = localStorage.getItem('audio_only') === 'true';
    var savedSubtitles = localStorage.getItem('subtitles') !== 'false'; // default to true
    
    audioCheckbox.checked = savedAudioOnly;
    subtitlesCheckbox.checked = savedSubtitles;
    
    // Save preferences on change
    audioCheckbox.addEventListener('change', function() {
        localStorage.setItem('audio_only', this.checked);
    });
    
    subtitlesCheckbox.addEventListener('change', function() {
        localStorage.setItem('subtitles', this.checked);
    });
})();
/* ── Metadata fetch on paste / type ─────────────────────────────────── */
(function() {
    var input = document.getElementById('urlInput');
    if (!input) { return; }
    var timeout = null;

    function tryFetch() {
        var val = input.value && input.value.trim();
        if (!val) { renderMetadata(null); return; }
        fetch('/metadata?url=' + encodeURIComponent(val))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) {
                    renderMetadata(null);
                    showMessage(data.error, 'error');
                } else {
                    renderMetadata((data && data.metadata) ? data.metadata : null, val);
                }
            })
            .catch(function(err) { 
                renderMetadata(null); 
                showMessage('Errore \'e rete o URL nun valida', 'error');
            });
    }

    input.addEventListener('paste', function() {
        topbarStart();
        setTimeout(tryFetch, 50);
    });
    input.addEventListener('input', function() {
        if (timeout) { clearTimeout(timeout); }
        if (!input.value || !input.value.trim()) { renderMetadata(null); return; }
        timeout = setTimeout(function() { topbarStart(); tryFetch(); }, 600);
    });
})();

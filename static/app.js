var DOWNLOAD_ID_KEY = 'yt_napoletano_download_id';
var _str = {};

/* ── i18n translations ───────────────────────────────────────────────── */
function applyI18nTranslations(strings) {
    _str = strings;
    document.querySelectorAll('[data-i18n]').forEach(function(el) {
        var parts = el.getAttribute('data-i18n').split('.');
        var val = strings;
        for (var i = 0; i < parts.length; i++) { val = val && val[parts[i]]; }
        if (val) el.textContent = val;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
        var parts = el.getAttribute('data-i18n-placeholder').split('.');
        var val = strings;
        for (var i = 0; i < parts.length; i++) { val = val && val[parts[i]]; }
        if (val) el.placeholder = val;
    });
}

function loadAndApplyTranslations() {
    fetch('/api/i18n/strings')
        .then(function(r) { return r.json(); })
        .then(applyI18nTranslations)
        .catch(function(err) { console.error('i18n load failed:', err); });
}

document.addEventListener('DOMContentLoaded', function() {
    var savedLang = localStorage.getItem('language') || 'nap';
    fetch('/api/i18n/set-language', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: savedLang })
    }).then(loadAndApplyTranslations);
});

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
    
    var detailsHint = (_str.messages && _str.messages.details_hint) || 'Click to see details';
    var closeLabel  = (_str.messages && _str.messages.close) || 'Close';
    var headerHtml = '<div class="message-icon">' + icon + '</div>' +
                     '<div class="message-main">' +
                     '  <div class="message-title">' + escapeHtml(displayTitle) + '</div>' +
                     (hasDetails ? '  <div class="message-hint">' + escapeHtml(detailsHint) + '</div>' : '') +
                     '</div>' +
                     '<button class="message-close" onclick="event.stopPropagation(); this.parentElement.remove()" aria-label="' + escapeHtml(closeLabel) + '">×</button>';
    el.innerHTML = headerHtml;
    
    if (hasDetails) {
        var detailsEl = document.createElement('div');
        detailsEl.className = 'message-details';
        var copyLabel = (_str.messages && _str.messages.copy_details) || '📋 Copy details';
        detailsEl.innerHTML = '<pre class="message-trace">' + escapeHtml(details) + '</pre>' +
                             '<button class="message-copy" onclick="event.stopPropagation(); copyToClipboard(this)">' + escapeHtml(copyLabel) + '</button>';
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
        btn.textContent = (_str.messages && _str.messages.copied) || '✓ Copied';
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
        showMessage((_str.messages && _str.messages.video_not_found) || 'Could not find the video.', 'error');
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
    showProgress('<span class="progress-icon">⬇️</span><span>' + (initialMessage || (_str.messages && _str.messages.starting) || 'Starting...') + '</span>');

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
        var fmt = (_str.progress && _str.progress.percent) || '{percent}% • {speed} • {size}';
        progressInfo.textContent = fmt.replace('{percent}', data.percent).replace('{speed}', data.speed).replace('{size}', data.size);
    });

    eventSource.addEventListener('complete', function(e) {
        downloadFinished = true;
        eventSource.close();
        hideProgress();
        clearDownloadId();
        showMessage(JSON.parse(e.data).message || (_str.download && _str.download.success) || 'Download complete!', 'success');
    });

    eventSource.addEventListener('error_event', function(e) {
        downloadFinished = true;
        eventSource.close();
        hideProgress();
        clearDownloadId();
        var data = JSON.parse(e.data);
        var errorMsg = data.error || (_str.download && _str.download.error_unknown) || 'Unknown error';
        var details = data.details || '';
        showMessage(errorMsg, 'error', details);
    });

    eventSource.onerror = function() {
        if (downloadFinished) { return; }
        eventSource.close();
        hideProgress();
        showMessage((_str.download && _str.download.connection_lost) || 'Connection lost – the download continues.', 'error');
    };
}

/* ── Form submit ─────────────────────────────────────────────────────── */
document.getElementById('downloadForm').onsubmit = function(event) {
    event.preventDefault();    var urlInput = document.getElementById('urlInput');
    if (!urlInput.value.trim()) {
        var errMsg = (_str.download && _str.download.error_invalid_url) || 'Please enter a valid URL';
        urlInput.setCustomValidity(errMsg);
        urlInput.reportValidity();
        return;
    }
    urlInput.setCustomValidity('');    var fd = new FormData(this);
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
                showMessage(data.last_message || (_str.download && _str.download.success) || 'Download complete!', 'success');
            } else if (data.status === 'error') {
                clearDownloadId();
                showMessage(data.error || (_str.download && _str.download.error) || 'Download failed', 'error');
            } else {
                if (data.metadata) { renderMetadata(data.metadata, data.url); }
                connectToDownloadStream(
                    '/download_stream?download_id=' + id,
                    (_str.messages && _str.messages.resuming) || 'Resuming previous download...'
                );
            }
        })
        .catch(function() { topbarDone(); });
});

/* ── Update yt-dlp and app ──────────────────────────────────────────── */
document.getElementById('updateLink').onclick = function(e) {
    if (e.preventDefault) e.preventDefault();
    document.getElementById('messageBox').innerHTML = '';
    topbarStart();
    var updateLink = document.getElementById('updateLink');
    updateLink.classList.add('updating');
    updateLink.disabled = true;

    fetch('/update', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            topbarDone();
            hideProgress();
            updateLink.classList.remove('updating');
            updateLink.disabled = false;
            var details = data.details ? '[' + new Date().toISOString() + ']\n' + data.details : '';
            showMessage(data.message || data.error, data.message ? 'success' : 'error', details);
        })
        .catch(function(err) {
            topbarDone();
            hideProgress();
            updateLink.classList.remove('updating');
            updateLink.disabled = false;
            var details = '[' + new Date().toISOString() + ']\n' + err.message;
            showMessage((_str.messages && _str.messages.network_error) || 'Network error', 'error', details);
        });
};
/* ── Theme toggle ──────────────────────────────────────────────────── */
(function() {
    var themeToggleBtn = document.getElementById('themeToggleBtn');
    var savedTheme = localStorage.getItem('theme') || 'dark';
    
    function applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-mode');
        } else {
            document.body.classList.remove('light-mode');
        }
        localStorage.setItem('theme', theme);
    }
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            var current = localStorage.getItem('theme') || 'dark';
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }
    
    // Apply saved theme on load
    applyTheme(savedTheme);
})();

/* ── Settings Drawer ─────────────────────────────────────────────────── */
(function() {
    var settingsBtn = document.getElementById('settingsBtn');
    var closeBtn = document.getElementById('closeSettingsBtn');
    var backdrop = document.getElementById('settingsBackdrop');
    var drawer = document.getElementById('settingsDrawer');
    
    function openDrawer() {
        drawer.classList.add('open');
        backdrop.classList.add('open');
    }
    
    function closeDrawer() {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
    }
    
    settingsBtn.addEventListener('click', function(e) {
        e.preventDefault();
        openDrawer();
    });
    
    closeBtn.addEventListener('click', function() {
        closeDrawer();
    });
    
    backdrop.addEventListener('click', function() {
        closeDrawer();
    });
    
    // Prevent close when clicking inside drawer
    drawer.addEventListener('click', function(e) {
        e.stopPropagation();
    });
    
    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDrawer();
        }
    });
})();

/* ── Language selector ──────────────────────────────────────────────── */
(function() {
    var langSelector = document.getElementById('languageSelector');
    if (!langSelector) { return; }
    
    // Load available languages
    fetch('/api/i18n/languages')
        .then(function(r) { return r.json(); })
        .then(function(languages) {
            // Clear current options
            langSelector.innerHTML = '';
            
            // Add language options
            for (var code in languages) {
                if (languages.hasOwnProperty(code)) {
                    var option = document.createElement('option');
                    option.value = code;
                    option.textContent = languages[code];
                    langSelector.appendChild(option);
                }
            }
            
            // Load saved language preference
            var savedLang = localStorage.getItem('language') || 'nap';
            langSelector.value = savedLang;
        })
        .catch(function(err) {
            console.error('Failed to load languages:', err);
        });
    
    // Handle language change
    langSelector.addEventListener('change', function() {
        var newLang = this.value;
        localStorage.setItem('language', newLang);
        
        fetch('/api/i18n/set-language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: newLang })
        })
            .then(loadAndApplyTranslations)
            .catch(function(err) {
                console.error('Failed to set language:', err);
            });
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
                showMessage((_str.download && _str.download.metadata_error) || 'Network error', 'error');
            });
    }

    input.addEventListener('paste', function() {
        topbarStart();
        setTimeout(tryFetch, 50);
    });
    input.addEventListener('input', function() {
        input.setCustomValidity('');
        if (timeout) { clearTimeout(timeout); }
        if (!input.value || !input.value.trim()) { renderMetadata(null); return; }
        timeout = setTimeout(function() { topbarStart(); tryFetch(); }, 600);
    });
})();

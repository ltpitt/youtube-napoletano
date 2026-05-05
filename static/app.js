var DOWNLOAD_ID_KEY = 'yt_napoletano_download_id';
var BATCH_ID_KEY = 'yt_napoletano_batch_id';
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
    // Clean up any stale "updating" state (e.g., from page reload during update)
    var updateLink = document.getElementById('updateLink');
    if (updateLink) {
        updateLink.classList.remove('updating');
        updateLink.disabled = false;
    }

    // Wire up the progress-log expand/collapse toggle
    var logToggle = document.getElementById('progressLogToggle');
    if (logToggle) {
        logToggle.addEventListener('click', function() {
            var log = document.getElementById('progressLog');
            if (!log) { return; }
            log.classList.toggle('expanded');

        });
    }

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

function storeBatchId(id) { localStorage.setItem(BATCH_ID_KEY, id); }
function clearBatchId()   { localStorage.removeItem(BATCH_ID_KEY); }
function getStoredBatchId() { return localStorage.getItem(BATCH_ID_KEY); }

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
    var pre = btn.parentElement.querySelector('pre');
    if (!pre) { return; }
    var details = pre.textContent;

    // Prefer modern Clipboard API when available (requires secure context on some mobile browsers)
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(details).then(function() {
            var orig = btn.textContent;
            btn.textContent = (_str.messages && _str.messages.copied) || '✓ Copied';
            setTimeout(function() { btn.textContent = orig; }, 2000);
        }).catch(function(err) {
            // Fallback to execCommand approach if Clipboard API fails
            fallbackCopyText(details, btn);
        });
        return;
    }

    // Older browsers (or restrictive mobile browsers): use fallback
    fallbackCopyText(details, btn);
}

function fallbackCopyText(text, btn) {
    try {
        var ta = document.createElement('textarea');
        ta.value = text;
        // Prevent mobile viewport from jumping
        ta.style.position = 'fixed';
        ta.style.top = '0';
        ta.style.left = '0';
        ta.style.width = '1px';
        ta.style.height = '1px';
        ta.style.padding = '0';
        ta.style.border = 'none';
        ta.style.outline = 'none';
        ta.style.boxShadow = 'none';
        ta.style.background = 'transparent';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        var successful = false;
        try {
            successful = document.execCommand('copy');
        } catch (e) {
            successful = false;
        }
        document.body.removeChild(ta);
        if (successful) {
            var orig = btn.textContent;
            btn.textContent = (_str.messages && _str.messages.copied) || '✓ Copied';
            setTimeout(function() { btn.textContent = orig; }, 2000);
            return true;
        }
    } catch (e) {
        // ignore
    }
    // If we reach here, copying failed — show a brief alert as fallback
    try { alert((_str.messages && _str.messages.copy_failed) || 'Copy failed — select and copy manually'); } catch (e) {}
    return false;
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
    clearProgressLog();
}
function showProgressIndeterminate(headerHtml) {
    var c  = document.getElementById('progressContainer');
    var pb = document.getElementById('progressBar');
    var ph = c.querySelector('.progress-header');
    c.style.display = 'block';
    pb.className = 'progress-bar indeterminate';
    ph.innerHTML = headerHtml;
    document.getElementById('progressInfo').textContent = '';
    clearProgressLog();
}
function hideProgress() {
    document.getElementById('progressContainer').style.display = 'none';
    document.getElementById('progressBar').className = 'progress-bar';
}

function clearProgressLog() {
    var toggle = document.getElementById('progressLogToggle');
    var log    = document.getElementById('progressLog');
    if (toggle) { toggle.style.display = 'none'; toggle.textContent = ''; }
    if (log)    { log.classList.remove('expanded'); var pre = log.querySelector('pre'); if (pre) { pre.textContent = ''; } }
}

function appendProgressLog(line) {
    var toggle = document.getElementById('progressLogToggle');
    var log    = document.getElementById('progressLog');
    if (!toggle || !log) { return; }
    var pre = log.querySelector('pre');
    if (!pre) { pre = document.createElement('pre'); pre.className = 'progress-log-trace'; log.appendChild(pre); }
    pre.textContent += (pre.textContent ? '\n' : '') + line;
    // Auto-scroll to bottom when expanded
    if (log.classList.contains('expanded')) { pre.scrollTop = pre.scrollHeight; }
    var hint = (_str.messages && _str.messages.details_hint) || 'Click to see details';
    toggle.textContent = hint;
    toggle.style.display = 'block';
}

function closeSettingsDrawer() {
    var backdrop = document.getElementById('settingsBackdrop');
    var drawer = document.getElementById('settingsDrawer');
    if (drawer) { drawer.classList.remove('open'); }
    if (backdrop) { backdrop.classList.remove('open'); }
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
        if (data.message) {
            if (data.message.startsWith('[')) {
                appendProgressLog(data.message);
            } else {
                progressInfo.textContent = data.message;
            }
        }
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

/* ── Add/Remove URL rows ─────────────────────────────────────────────── */
(function() {
    var addBtn = document.getElementById('addUrlBtn');
    if (!addBtn) { return; }

    addBtn.addEventListener('click', function() {
        var urlList = document.getElementById('urlList');
        var row = document.createElement('div');
        row.className = 'url-row';
        var placeholder = (_str.download && _str.download.placeholder) || "Miette ccà 'o link d''o video 'e YouTube";
        var removeLabel = (_str.batch && _str.batch.remove_url) || 'Remove';
        row.innerHTML = '<input type="text" name="url" class="url-input" placeholder="' + escapeHtml(placeholder) + '" data-i18n-placeholder="download.placeholder">' +
                        '<button type="button" class="remove-url-btn" aria-label="' + escapeHtml(removeLabel) + '" title="' + escapeHtml(removeLabel) + '">✕</button>';
        urlList.appendChild(row);
        row.querySelector('.url-input').focus();
        row.querySelector('.remove-url-btn').addEventListener('click', function() {
            row.remove();
        });
    });
})();

/* ── Collect URLs from form ──────────────────────────────────────────── */
function collectUrls() {
    var inputs = document.querySelectorAll('#urlList .url-input');
    var urls = [];
    for (var i = 0; i < inputs.length; i++) {
        var val = inputs[i].value && inputs[i].value.trim();
        if (val) { urls.push(val); }
    }
    return urls;
}

/* ── Batch SSE stream ────────────────────────────────────────────────── */
function connectToBatchStream(batchId, total) {
    var messageBox   = document.getElementById('messageBox');
    var progressBar  = document.getElementById('progressBar');
    var progressInfo = document.getElementById('progressInfo');

    messageBox.innerHTML = '';
    topbarStart();
    showProgress('<span class="progress-icon">⬇️</span><span>' + ((_str.batch && _str.batch.downloading_item) || 'Downloading {current} of {total}...').replace('{current}', '1').replace('{total}', total) + '</span>');

    var eventSource = new EventSource('/batch/stream/' + batchId);
    var batchFinished = false;

    eventSource.addEventListener('batch_snapshot', function(e) {
        topbarDone();
        var data = JSON.parse(e.data);
        // Count completed items
        var completed = 0;
        for (var i = 0; i < data.items.length; i++) {
            if (data.items[i].status === 'complete' || data.items[i].status === 'error') { completed++; }
        }
        if (completed > 0 && completed < data.items.length) {
            var fmt = (_str.batch && _str.batch.downloading_item) || 'Downloading {current} of {total}...';
            var ph = document.querySelector('.progress-header');
            if (ph) { ph.innerHTML = '<span class="progress-icon">⬇️</span><span>' + fmt.replace('{current}', (completed + 1).toString()).replace('{total}', data.items.length.toString()) + '</span>'; }
            progressInfo.textContent = '';
        }
    });

    eventSource.addEventListener('batch_item_start', function(e) {
        var data = JSON.parse(e.data);
        var current = data.index + 1;
        var fmt = (_str.batch && _str.batch.downloading_item) || 'Downloading {current} of {total}...';
        var ph = document.querySelector('.progress-header');
        if (ph) {
            ph.innerHTML = '<span class="progress-icon">⬇️</span><span>' + fmt.replace('{current}', current.toString()).replace('{total}', data.total.toString()) + '</span>';
        }
        progressBar.style.width = '0%';
        progressInfo.textContent = '';
        clearProgressLog();
    });

    eventSource.addEventListener('batch_item_progress', function(e) {
        var data = JSON.parse(e.data);
        var p = data.progress;
        progressBar.style.width = p.percent + '%';
        var fmt = (_str.progress && _str.progress.percent) || '{percent}% • {speed} • {size}';
        progressInfo.textContent = fmt.replace('{percent}', p.percent).replace('{speed}', p.speed).replace('{size}', p.size);
    });

    eventSource.addEventListener('batch_item_status', function(e) {
        var data = JSON.parse(e.data);
        if (data.message) {
            if (data.message.startsWith('[')) {
                appendProgressLog(data.message);
            } else {
                progressInfo.textContent = data.message;
                progressBar.className = 'progress-bar indeterminate';
            }
        }
    });

    eventSource.addEventListener('batch_item_complete', function(e) {
        var data = JSON.parse(e.data);
        var current = data.index + 1;
        var fmt = (_str.batch && _str.batch.item_complete) || 'Video {current} of {total} complete!';
        showMessage(fmt.replace('{current}', current.toString()).replace('{total}', data.total.toString()), 'success');
    });

    eventSource.addEventListener('batch_item_error', function(e) {
        var data = JSON.parse(e.data);
        var current = data.index + 1;
        var fmt = (_str.batch && _str.batch.item_error) || 'Error with video {current} of {total}';
        showMessage(fmt.replace('{current}', current.toString()).replace('{total}', (total || '?').toString()), 'error', data.error || '');
    });

    eventSource.addEventListener('batch_waiting', function(e) {
        var data = JSON.parse(e.data);
        progressInfo.textContent = (_str.batch && _str.batch.waiting_next) || 'Waiting before next download...';
        progressBar.className = 'progress-bar indeterminate';
    });

    eventSource.addEventListener('batch_heartbeat', function(e) {
        // Server is alive and the download is still running - keep bar animated
        if (progressBar.className.indexOf('indeterminate') === -1) {
            progressBar.className = 'progress-bar indeterminate';
        }
    });

    eventSource.addEventListener('batch_complete', function(e) {
        batchFinished = true;
        eventSource.close();
        hideProgress();
        clearBatchId();
        var data = JSON.parse(e.data);
        var fmt = (_str.batch && _str.batch.batch_complete) || 'All {total} videos downloaded!';
        showMessage(fmt.replace('{total}', data.total.toString()), 'success');
    });

    eventSource.addEventListener('error_event', function(e) {
        batchFinished = true;
        eventSource.close();
        hideProgress();
        clearBatchId();
        var data = JSON.parse(e.data);
        showMessage(data.error || 'Error', 'error');
    });

    eventSource.onerror = function() {
        if (batchFinished) { return; }
        eventSource.close();
        hideProgress();
        showMessage((_str.download && _str.download.connection_lost) || 'Connection lost – downloads continue in background.', 'error');
    };
}

/* ── Form submit ─────────────────────────────────────────────────────── */
document.getElementById('downloadForm').onsubmit = function(event) {
    event.preventDefault();
    var urls = collectUrls();
    if (urls.length === 0) {
        var firstInput = document.querySelector('#urlList .url-input');
        if (firstInput) {
            var errMsg = (_str.download && _str.download.error_invalid_url) || 'Please enter a valid URL';
            firstInput.setCustomValidity(errMsg);
            firstInput.reportValidity();
        }
        return;
    }
    // Clear validation state
    var allInputs = document.querySelectorAll('#urlList .url-input');
    for (var i = 0; i < allInputs.length; i++) { allInputs[i].setCustomValidity(''); }

    var fd = new FormData(this);
    var audioOnly = fd.get('audio_only') ? true : false;
    var subtitles = fd.get('subtitles') ? true : false;

    if (urls.length === 1) {
        // Single URL: use existing streaming endpoint
        connectToDownloadStream(
            '/download_stream?url=' + encodeURIComponent(urls[0]) +
            '&audio_only=' + (audioOnly ? 'true' : 'false') +
            '&subtitles=' + (subtitles ? 'true' : 'false')
        );
    } else {
        // Multiple URLs: use batch endpoint
        document.getElementById('messageBox').innerHTML = '';
        topbarStart();
        showProgress('<span class="progress-icon">⬇️</span><span>' + ((_str.messages && _str.messages.starting) || 'Starting...') + '</span>');

        var batchPayload = { urls: urls, audio_only: audioOnly, subtitles: subtitles };

        fetch('/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(batchPayload)
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.error) {
                topbarDone();
                hideProgress();
                showMessage(data.error, 'error');
                return;
            }
            storeBatchId(data.batch_id);
            topbarDone();
            connectToBatchStream(data.batch_id, data.total);
        })
        .catch(function(err) {
            topbarDone();
            hideProgress();
            showMessage((_str.messages && _str.messages.network_error) || 'Network error', 'error');
        });
    }
};

/* ── Resume on page load ─────────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', function() {
    // Check for a batch in progress first
    var batchId = getStoredBatchId();
    if (batchId) {
        topbarStart();
        fetch('/batch/status/' + batchId)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                topbarDone();
                if (data.error) { clearBatchId(); return; }
                if (data.status === 'complete') {
                    clearBatchId();
                    var fmt = (_str.batch && _str.batch.batch_complete) || 'All {total} videos downloaded!';
                    showMessage(fmt.replace('{total}', data.items.length.toString()), 'success');
                } else {
                    connectToBatchStream(batchId, data.items.length);
                }
            })
            .catch(function() { topbarDone(); clearBatchId(); });
        return;
    }

    // Check for a single download in progress
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
function isTransientNetworkError(err) {
    if (!err) return false;
    var msg = String(err.message || err.toString() || '').toLowerCase();
    return err.name === 'TypeError' ||
           msg.indexOf('networkerror') !== -1 ||
           msg.indexOf('failed to fetch') !== -1 ||
           msg.indexOf('network request failed') !== -1;
}

function waitForServerRecovery(timeoutMs, intervalMs) {
    var startedAt = Date.now();

    return new Promise(function(resolve) {
        function probe() {
            fetch('/healthz', {
                method: 'GET',
                cache: 'no-store',
                headers: { 'Cache-Control': 'no-cache' }
            })
                .then(function(r) {
                    if (r.ok) {
                        resolve(true);
                        return;
                    }

                    if (Date.now() - startedAt >= timeoutMs) {
                        resolve(false);
                        return;
                    }
                    setTimeout(probe, intervalMs);
                })
                .catch(function() {
                    if (Date.now() - startedAt >= timeoutMs) {
                        resolve(false);
                        return;
                    }
                    setTimeout(probe, intervalMs);
                });
        }

        probe();
    });
}

function requestUpdate() {
    return fetch('/update', { method: 'POST' })
        .then(function(r) {
            if (!r.ok) {
                return r.json().then(function(data) {
                    throw new Error(data.error || data.message || 'Update failed with status ' + r.status);
                }).catch(function() {
                    throw new Error('Update failed with status ' + r.status);
                });
            }
            return r.json();
        });
}

document.getElementById('updateLink').onclick = function(e) {
    if (e.preventDefault) e.preventDefault();
    document.getElementById('messageBox').innerHTML = '';
    topbarStart();
    showProgressIndeterminate('<span class="progress-icon">⟳</span><span>' + ((_str.update && _str.update.updating_app) || 'Updating...') + '</span>');
    var updateLink = document.getElementById('updateLink');
    updateLink.classList.add('updating');
    updateLink.disabled = true;

    closeSettingsDrawer();

    function finishSuccess(data) {
        topbarDone();
        hideProgress();
        updateLink.classList.remove('updating');
        updateLink.disabled = false;
        var details = data.details ? '[' + new Date().toISOString() + ']\n' + data.details : '';
        showMessage(data.message || 'Update completed', 'success', details);
    }

    function finishError(err) {
        topbarDone();
        hideProgress();
        updateLink.classList.remove('updating');
        updateLink.disabled = false;
        var details = '[' + new Date().toISOString() + ']\n' + (err.message || err.toString());
        showMessage(err.message || ((_str.messages && _str.messages.network_error) || 'Update failed'), 'error', details);
    }

    function attemptUpdate(attemptNo) {
        requestUpdate()
            .then(function(data) {
                finishSuccess(data);
            })
            .catch(function(err) {
                if (isTransientNetworkError(err) && attemptNo < 2) {
                    showProgressIndeterminate('<span class="progress-icon">⟳</span><span>' + ((_str.update && _str.update.updating_app) || 'Updating...') + '</span>');
                    waitForServerRecovery(45000, 1200)
                        .then(function(recovered) {
                            if (!recovered) {
                                finishError(err);
                                return;
                            }
                            attemptUpdate(attemptNo + 1);
                        })
                        .catch(function() {
                            finishError(err);
                        });
                    return;
                }
                finishError(err);
            });
    }

    attemptUpdate(1);
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
    var urlList = document.getElementById('urlList');
    if (!urlList) { return; }
    var timeout = null;

    function tryFetch(input) {
        var val = input && input.value && input.value.trim();
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

    // Use event delegation on the url list container
    urlList.addEventListener('paste', function(e) {
        if (e.target.classList.contains('url-input')) {
            topbarStart();
            var target = e.target;
            setTimeout(function() { tryFetch(target); }, 50);
        }
    });
    urlList.addEventListener('input', function(e) {
        if (!e.target.classList.contains('url-input')) { return; }
        e.target.setCustomValidity('');
        if (timeout) { clearTimeout(timeout); }
        if (!e.target.value || !e.target.value.trim()) { renderMetadata(null); return; }
        var target = e.target;
        timeout = setTimeout(function() { topbarStart(); tryFetch(target); }, 600);
    });
})();

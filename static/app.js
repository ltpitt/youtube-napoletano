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

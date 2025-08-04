document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('ttsForm');
    const textInput = document.getElementById('textInput');
    const voiceSelect = document.getElementById('voiceSelect');
    const generateBtn = document.getElementById('generateBtn');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    const audioPlayer = document.getElementById('audioPlayer');
    const audioUrl = document.getElementById('audioUrl');
    const errorMessage = document.getElementById('errorMessage');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const text = textInput.value.trim();
        const voice_id = voiceSelect.value;
        
        if (!text) {
            showError('Please enter some text to convert to speech.');
            return;
        }
        
        hideAllMessages();
        showLoading();
        generateBtn.disabled = true;
        
        try {
            const response = await fetch('/generate-audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    voice_id: voice_id
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                showResult(data.audio_url);
            } else {
                showError(data.detail || 'Failed to generate speech');
            }
        } catch (err) {
            showError('Network error: ' + err.message);
        } finally {
            hideLoading();
            generateBtn.disabled = false;
        }
    });

    function showLoading() {
        loading.classList.remove('hidden');
    }
    
    function hideLoading() {
        loading.classList.add('hidden');
    }
    
    function showResult(url) {
        console.log('Audio URL received:', url);
        audioPlayer.src = url;
        audioUrl.textContent = url;
        audioPlayer.load();
        result.classList.remove('hidden');
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        error.classList.remove('hidden');
    }
    
    function hideAllMessages() {
        loading.classList.add('hidden');
        result.classList.add('hidden');
        error.classList.add('hidden');
    }
    
    textInput.addEventListener('input', function() {
        if (this.value.length > 500) {
            this.value = this.value.substring(0, 500);
        }
    });
});

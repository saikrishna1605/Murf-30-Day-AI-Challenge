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

    // Echo Bot functionality
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const audioPlayback = document.getElementById('audioPlayback');
    const recordingIndicator = document.getElementById('recordingIndicator');
    let mediaRecorder;
    let audioChunks = [];

    // Check if elements exist before adding event listeners
    if (startRecordingBtn && stopRecordingBtn && audioPlayback && recordingIndicator) {
        startRecordingBtn.addEventListener('click', async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                audioChunks = [];

                mediaRecorder.addEventListener('dataavailable', event => {
                    audioChunks.push(event.data);
                });

                // Update UI
                startRecordingBtn.disabled = true;
                stopRecordingBtn.disabled = false;
                recordingIndicator.classList.add('active');
                
                // Simple visual feedback without complex animations
                startRecordingBtn.style.opacity = '0.5';
                stopRecordingBtn.style.transform = 'scale(1.02)';
                
            } catch (error) {
                console.error('Error accessing microphone:', error);
                showError('Could not access microphone. Please check permissions and ensure you are using HTTPS.');
            }
        });

        stopRecordingBtn.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                
                mediaRecorder.addEventListener('stop', () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    audioPlayback.src = audioUrl;
                    audioPlayback.load();
                    uploadAudio(audioBlob);
                });

                // Stop all tracks to release microphone
                const stream = mediaRecorder.stream;
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
            }

            // Update UI
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
            recordingIndicator.classList.remove('active');
            
            // Reset visual feedback
            startRecordingBtn.style.opacity = '1';
            stopRecordingBtn.style.transform = 'scale(1)';
        });

        async function uploadAudio(audioBlob) {
            const uploadStatus = document.getElementById('uploadStatus');
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');
    
            try {
                uploadStatus.textContent = 'Uploading audio...';
                const response = await fetch('/upload-audio', {
                    method: 'POST',
                    body: formData
                });
    
                if (response.ok) {
                    const result = await response.json();
                    uploadStatus.innerHTML = `
                        Upload successful!<br>
                        File: ${result.filename}<br>
                        Type: ${result.content_type}<br>
                        Size: ${result.size} bytes
                    `;
                } else {
                    uploadStatus.textContent = `Upload failed: ${response.statusText}`;
                }
            } catch (error) {
                uploadStatus.textContent = `Error uploading audio: ${error.message}`;
            }
        }
    } else {
        console.error('Echo bot elements not found');
    }
});

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
    const transcribeContainer = document.getElementById('transcribeContainer');
    const transcribeBtn = document.getElementById('transcribeBtn');
    const transcribingStatus = document.getElementById('transcribingStatus');
    const transcriptionResult = document.getElementById('transcriptionResult');
    const transcriptionText = document.getElementById('transcriptionText');
    let mediaRecorder;
    let audioChunks = [];
    let audioBlob;

    // Check if elements exist before adding event listeners
    if (startRecordingBtn && stopRecordingBtn && audioPlayback && recordingIndicator) {
        startRecordingBtn.addEventListener('click', async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };
                mediaRecorder.onstop = async () => {
                    audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    audioChunks = [];
                    
                    stopRecordingBtn.disabled = true;
                    startRecordingBtn.disabled = false;
                    recordingIndicator.classList.add('hidden');
                    
                    // Automatically process the audio with Murf
                    await processEchoAudio();
                };
                mediaRecorder.start();
                startRecordingBtn.disabled = true;
                stopRecordingBtn.disabled = false;
                recordingIndicator.classList.remove('hidden');
                audioPlayback.classList.add('hidden');
                transcribeContainer.classList.add('hidden');
                transcriptionResult.classList.add('hidden');
            } catch (err) {
                showError('Could not start recording: ' + err.message);
            }
        });

        stopRecordingBtn.addEventListener('click', () => {
            mediaRecorder.stop();
        });

        // Function to automatically process echo audio
        async function processEchoAudio() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            // Show processing status
            transcribingStatus.textContent = 'Processing echo...';
            transcribingStatus.classList.remove('hidden');
            transcribeContainer.classList.remove('hidden');
            transcribeBtn.disabled = true;

            try {
                const response = await fetch('/tts/echo', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    // Show what was transcribed
                    transcriptionText.textContent = data.transcription;
                    transcriptionResult.classList.remove('hidden');
                    
                    // Automatically play the Murf-generated audio
                    if (data.audio_url) {
                        audioPlayback.src = data.audio_url;
                        audioPlayback.classList.remove('hidden');
                        audioPlayback.load();
                        console.log('Echo: Auto-playing Murf-generated audio:', data.audio_url);
                        
                        // Auto-play the audio
                        try {
                            await audioPlayback.play();
                        } catch (playError) {
                            console.log('Auto-play prevented by browser, user can manually play');
                        }
                    }
                } else {
                    showError(data.detail || 'Failed to process echo');
                }
            } catch (err) {
                showError('Network error: ' + err.message);
            } finally {
                transcribingStatus.classList.add('hidden');
                transcribeBtn.disabled = false;
            }
        }

        // Keep the manual button for backup/re-processing
        transcribeBtn.addEventListener('click', async () => {
            await processEchoAudio();
        });
    }
});

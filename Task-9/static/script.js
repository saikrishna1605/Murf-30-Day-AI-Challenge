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

    // Enhanced AI Voice Agent functionality (Echo Bot v3)
    const startRecordingBtn = document.getElementById('startRecording');
    const stopRecordingBtn = document.getElementById('stopRecording');
    const audioPlayback = document.getElementById('audioPlayback');
    const recordingIndicator = document.getElementById('recordingIndicator');
    const processingIndicator = document.getElementById('processingIndicator');
    const transcribeContainer = document.getElementById('transcribeContainer');
    const transcribeBtn = document.getElementById('transcribeBtn');
    const transcribingStatus = document.getElementById('transcribingStatus');
    const transcriptionResult = document.getElementById('transcriptionResult');
    const transcriptionText = document.getElementById('transcriptionText');
    const recordingText = document.getElementById('recordingText');
    const processingText = document.getElementById('processingText');
    const resultTitle = document.getElementById('resultTitle');
    const llmResponseSection = document.getElementById('llmResponseSection');
    const llmResponseText = document.getElementById('llmResponseText');
    const modeButtons = document.querySelectorAll('.mode-btn');
    
    let mediaRecorder;
    let audioChunks = [];
    let audioBlob;
    let currentMode = 'echo'; // default mode

    // Mode change handler for buttons
    if (modeButtons.length > 0) {
        console.log('Found', modeButtons.length, 'mode buttons');
        modeButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                console.log('Mode button clicked:', this.getAttribute('data-mode'));
                
                // Remove active class from all buttons
                modeButtons.forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                this.classList.add('active');
                
                currentMode = this.getAttribute('data-mode');
                console.log('Current mode changed to:', currentMode);
                updateUIForMode();
            });
        });
    } else {
        console.log('No mode buttons found');
    }

    function updateUIForMode() {
        console.log('Updating UI for mode:', currentMode);
        if (currentMode === 'echo') {
            if (recordingText) recordingText.textContent = 'Recording for echo...';
            if (processingText) processingText.textContent = 'Processing echo...';
            if (resultTitle) resultTitle.textContent = 'What you said:';
        } else {
            if (recordingText) recordingText.textContent = 'Recording your question...';
            if (processingText) processingText.textContent = 'AI is thinking and preparing response...';
            if (resultTitle) resultTitle.textContent = 'Your Question:';
        }
    }

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
                    
                    // Process the audio based on current mode
                    if (currentMode === 'echo') {
                        await processEchoAudio();
                    } else {
                        await processLLMAudio();
                    }
                };
                mediaRecorder.start();
                startRecordingBtn.disabled = true;
                stopRecordingBtn.disabled = false;
                recordingIndicator.classList.remove('hidden');
                audioPlayback.classList.add('hidden');
                if (transcribeContainer) transcribeContainer.classList.add('hidden');
                if (transcriptionResult) transcriptionResult.classList.add('hidden');
            } catch (err) {
                showError('Could not start recording: ' + err.message);
            }
        });

        stopRecordingBtn.addEventListener('click', () => {
            mediaRecorder.stop();
        });

        // Function to process echo audio (original functionality)
        async function processEchoAudio() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            // Show processing status
            if (processingIndicator) processingIndicator.classList.remove('hidden');
            if (transcribeContainer) transcribeContainer.classList.remove('hidden');

            try {
                const response = await fetch('/tts/echo', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    // Show what was transcribed
                    if (transcriptionText) transcriptionText.textContent = data.transcription;
                    if (transcriptionResult) transcriptionResult.classList.remove('hidden');
                    if (llmResponseSection) llmResponseSection.classList.add('hidden'); // Hide LLM section in echo mode
                    
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
                if (processingIndicator) processingIndicator.classList.add('hidden');
            }
        }

        // Function to process audio through LLM pipeline
        async function processLLMAudio() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            // Show processing status
            if (processingIndicator) processingIndicator.classList.remove('hidden');
            if (transcribeContainer) transcribeContainer.classList.remove('hidden');

            try {
                const response = await fetch('/llm/query', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    // Show the conversation
                    if (transcriptionText) transcriptionText.textContent = data.transcription;
                    if (llmResponseText) llmResponseText.textContent = data.llm_response;
                    if (transcriptionResult) transcriptionResult.classList.remove('hidden');
                    if (llmResponseSection) llmResponseSection.classList.remove('hidden'); // Show LLM response section
                    
                    // Play the AI's voice response
                    if (data.audio_url) {
                        audioPlayback.src = data.audio_url;
                        audioPlayback.classList.remove('hidden');
                        audioPlayback.load();
                        console.log('AI Voice Agent: Playing AI response:', data.audio_url);
                        
                        // Auto-play the AI response
                        try {
                            await audioPlayback.play();
                        } catch (playError) {
                            console.log('Auto-play prevented by browser, user can manually play');
                        }
                    }
                } else {
                    showError(data.detail || 'Failed to process LLM query');
                }
            } catch (err) {
                showError('Network error: ' + err.message);
            } finally {
                if (processingIndicator) processingIndicator.classList.add('hidden');
            }
        }

        // Keep the manual button for backup/re-processing
        if (transcribeBtn) {
            transcribeBtn.addEventListener('click', async () => {
                if (currentMode === 'echo') {
                    await processEchoAudio();
                } else {
                    await processLLMAudio();
                }
            });
        }
    }

    // Initialize UI for default mode
    updateUIForMode();
});

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
        
        if (text.length > 5000) {
            showError('Text is too long. Please keep it under 5000 characters.');
            return;
        }
        
        hideAllMessages();
        generateBtn.disabled = true;
        showLoading();
        
        try {
            // Set a timeout for the request
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
            
            const response = await fetch('/generate-audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    voice_id: voice_id
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                showResult(data.audio_url);
            } else {
                // Handle structured error responses
                let errorMsg = 'Failed to generate speech';
                if (data.detail) {
                    if (typeof data.detail === 'object' && data.detail.fallback) {
                        errorMsg = data.detail.fallback;
                    } else if (typeof data.detail === 'string') {
                        errorMsg = data.detail;
                    }
                }
                showError(errorMsg);
            }
        } catch (err) {
            console.error('TTS Error:', err);
            let errorMessage = 'Network error occurred';
            
            if (err.name === 'AbortError') {
                errorMessage = 'Request timed out. The text might be too long or the service is busy. Please try again.';
            } else if (err.message.includes('Failed to fetch')) {
                errorMessage = 'Unable to connect to the speech service. Please check your internet connection and try again.';
            } else {
                errorMessage = 'Something went wrong while generating speech. Please try again.';
            }
            
            showError(errorMessage);
        } finally {
            generateBtn.disabled = false;
            hideLoading();
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
        
        // Read out the error message
        readErrorMessage(message);
    }
    
    // Function to read out error messages using TTS
    async function readErrorMessage(message) {
        // Check if error readout is enabled
        if (!isErrorReadoutEnabled) {
            console.log('Error readout disabled by user');
            return;
        }
        
        try {
            // First try to use the server's TTS for error audio
            const response = await fetch('/generate-error-audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success' && data.audio_url) {
                // Play the server-generated error audio
                const errorAudio = new Audio(data.audio_url);
                errorAudio.volume = 0.8;
                
                errorAudio.play().catch(playError => {
                    console.log('Server TTS error audio play failed, trying browser TTS');
                    fallbackToSpeechSynthesis(message);
                });
                
                console.log('Playing server-generated error audio');
                return;
            }
        } catch (err) {
            console.log('Server error audio failed, using browser TTS');
        }
        
        // Fallback to browser's built-in Speech Synthesis
        fallbackToSpeechSynthesis(message);
    }
    
    // Fallback function using browser's Speech Synthesis API
    function fallbackToSpeechSynthesis(message) {
        if ('speechSynthesis' in window) {
            // Cancel any ongoing speech
            speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(message);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            utterance.volume = 0.8;
            
            // Try to use a more serious voice for errors
            const voices = speechSynthesis.getVoices();
            const preferredVoice = voices.find(voice => 
                voice.name.includes('Microsoft') || 
                voice.name.includes('Google') ||
                voice.name.includes('Alex') ||
                voice.default
            );
            
            if (preferredVoice) {
                utterance.voice = preferredVoice;
            }
            
            utterance.onstart = () => {
                console.log('Reading error message with browser TTS');
            };
            
            utterance.onerror = (event) => {
                console.error('Speech synthesis failed:', event.error);
            };
            
            speechSynthesis.speak(utterance);
        } else {
            console.log('Speech synthesis not supported in this browser');
        }
    }
    
    function hideAllMessages() {
        loading.classList.add('hidden');
        result.classList.add('hidden');
        error.classList.add('hidden');
    }
    
    // Enhanced error handling functions
    function displaySuccessfulResult(data, mode) {
        // Show transcription
        if (transcriptionText) transcriptionText.textContent = data.transcription || '';
        if (transcriptionResult) transcriptionResult.classList.remove('hidden');
        
        // Handle mode-specific display
        if (mode === 'echo') {
            if (llmResponseSection) llmResponseSection.classList.add('hidden');
        } else {
            // Show LLM response for chat/llm modes
            if (llmResponseSection && data.llm_response) {
                llmResponseSection.classList.remove('hidden');
                if (llmResponseText) llmResponseText.textContent = data.llm_response;
            }
            
            // Show chat info if available
            if (mode === 'chat' && chatInfo && data.message_count !== undefined) {
                chatInfo.classList.remove('hidden');
                if (messageCount) messageCount.textContent = data.message_count;
            }
        }
        
        // Play audio if available
        if (data.audio_url) {
            audioPlayback.src = data.audio_url;
            audioPlayback.classList.remove('hidden');
            audioPlayback.load();
            
            // Auto-play the audio
            audioPlayback.play().catch(playError => {
                console.log('Auto-play prevented by browser, user can manually play');
            });
        }
    }
    
    function displayPartialResult(data, mode) {
        // Show what was processed
        if (transcriptionText) transcriptionText.textContent = data.transcription || 'Audio processed';
        if (transcriptionResult) transcriptionResult.classList.remove('hidden');
        
        // Show LLM response if available
        if (data.llm_response && llmResponseSection) {
            llmResponseSection.classList.remove('hidden');
            if (llmResponseText) llmResponseText.textContent = data.llm_response;
        }
        
        // Show fallback message and read it out
        let errorMsg = '';
        if (data.fallback_text) {
            errorMsg = data.fallback_text + ' (Partial processing completed)';
        } else if (data.message) {
            errorMsg = data.message;
        } else {
            errorMsg = 'Some services are experiencing issues, but partial processing completed.';
        }
        
        showError(errorMsg);
        
        // Update chat info if available
        if (mode === 'chat' && chatInfo && data.message_count !== undefined) {
            chatInfo.classList.remove('hidden');
            if (messageCount) messageCount.textContent = data.message_count;
        }
    }
    
    function displayFallbackResult(data, mode) {
        let errorMsg = '';
        if (data.fallback_text) {
            errorMsg = data.fallback_text;
        } else {
            errorMsg = 'Service temporarily unavailable. Please try again.';
        }
        
        // If there's audio available for the fallback, play it instead of TTS
        if (data.audio_url) {
            // Show transcription if available
            if (data.transcription) {
                if (transcriptionText) transcriptionText.textContent = data.transcription;
                if (transcriptionResult) transcriptionResult.classList.remove('hidden');
            }
            
            // Play the fallback audio directly
            audioPlayback.src = data.audio_url;
            audioPlayback.classList.remove('hidden');
            audioPlayback.load();
            
            // Also show the error message visually
            errorMessage.textContent = errorMsg;
            error.classList.remove('hidden');
            
            audioPlayback.play().catch(playError => {
                console.log('Fallback audio play failed, using TTS for error');
                readErrorMessage(errorMsg);
            });
        } else {
            showError(errorMsg);
        }
        
        // Show transcription if available
        if (data.transcription) {
            if (transcriptionText) transcriptionText.textContent = data.transcription;
            if (transcriptionResult) transcriptionResult.classList.remove('hidden');
        }
    }
    
    function handleAPIError(data, statusCode) {
        let errorMessage = 'Service error occurred';
        
        if (data.detail) {
            if (typeof data.detail === 'object' && data.detail.fallback) {
                errorMessage = data.detail.fallback;
            } else if (typeof data.detail === 'string') {
                errorMessage = data.detail;
            }
        }
        
        // Add status code context
        if (statusCode >= 500) {
            errorMessage = 'Server error: ' + errorMessage;
        } else if (statusCode === 429) {
            errorMessage = 'Too many requests. Please wait a moment and try again.';
        } else if (statusCode === 413) {
            errorMessage = 'Audio file too large. Please record a shorter message.';
        }
        
        showError(errorMessage);
    }
    
    function handleNetworkError(err, operation) {
        console.error(`Network error during ${operation}:`, err);
        let errorMessage = `Failed to ${operation}`;
        
        if (err.name === 'AbortError') {
            errorMessage = 'Request timed out. The service might be busy. Please try again.';
        } else if (err.message.includes('Failed to fetch')) {
            errorMessage = 'Unable to connect to the service. Please check your internet connection.';
        } else if (err.message.includes('NetworkError')) {
            errorMessage = 'Network connection problem. Please try again.';
        } else {
            errorMessage = 'Something went wrong. Please try again.';
        }
        
        showError(errorMessage);
    }
    
    textInput.addEventListener('input', function() {
        if (this.value.length > 500) {
            this.value = this.value.substring(0, 500);
        }
    });

    // Enhanced AI Voice Agent functionality (Echo Bot v4 - Chat History)
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
    const chatInfo = document.getElementById('chatInfo');
    const messageCount = document.getElementById('messageCount');
    const sessionIdElement = document.getElementById('sessionId');
    const newSessionBtn = document.getElementById('newSessionBtn');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    const viewSessionsBtn = document.getElementById('viewSessionsBtn');
    const sessionsModal = document.getElementById('sessionsModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    const sessionsList = document.getElementById('sessionsList');
    const errorReadoutToggle = document.getElementById('errorReadoutToggle');
    
    let mediaRecorder;
    let audioChunks = [];
    let audioBlob;
    let currentMode = 'echo'; // default mode
    let currentSessionId = generateSessionId();
    let isAutoRecordingEnabled = false;
    let isErrorReadoutEnabled = true; // New setting for error readouts

    // Load error readout setting from localStorage
    if (localStorage.getItem('errorReadoutEnabled') !== null) {
        isErrorReadoutEnabled = localStorage.getItem('errorReadoutEnabled') === 'true';
    }
    
    // Initialize toggle state
    if (errorReadoutToggle) {
        errorReadoutToggle.checked = isErrorReadoutEnabled;
        
        errorReadoutToggle.addEventListener('change', function() {
            isErrorReadoutEnabled = this.checked;
            localStorage.setItem('errorReadoutEnabled', isErrorReadoutEnabled);
            console.log('Error readout', isErrorReadoutEnabled ? 'enabled' : 'disabled');
            
            // Give feedback about the setting change
            const feedbackMsg = isErrorReadoutEnabled ? 
                'Error messages will now be read aloud' : 
                'Error message readouts disabled';
                
            // Show brief visual feedback
            const tempDiv = document.createElement('div');
            tempDiv.textContent = feedbackMsg;
            tempDiv.style.cssText = `
                position: fixed; top: 20px; right: 20px; 
                background: #4CAF50; color: white; 
                padding: 10px 15px; border-radius: 5px;
                z-index: 1000; font-size: 14px;
            `;
            document.body.appendChild(tempDiv);
            
            setTimeout(() => {
                document.body.removeChild(tempDiv);
            }, 3000);
            
            // If enabled, read out the confirmation
            if (isErrorReadoutEnabled) {
                fallbackToSpeechSynthesis('Error readouts enabled');
            }
        });
    }

    // Session management
    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    function updateSessionDisplay() {
        if (sessionIdElement) {
            sessionIdElement.textContent = currentSessionId;
        }
        // Update URL with session ID
        const url = new URL(window.location);
        url.searchParams.set('session_id', currentSessionId);
        window.history.replaceState({}, '', url);
    }

    // Initialize session from URL or generate new one
    function initializeSession() {
        const urlParams = new URLSearchParams(window.location.search);
        const sessionFromUrl = urlParams.get('session_id');
        
        if (sessionFromUrl && sessionFromUrl.trim() !== '') {
            currentSessionId = sessionFromUrl;
        } else {
            currentSessionId = generateSessionId();
        }
        
        updateSessionDisplay();
    }

    // Session button handlers
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', () => {
            currentSessionId = generateSessionId();
            updateSessionDisplay();
            // Clear current conversation display
            if (transcriptionResult) transcriptionResult.classList.add('hidden');
            if (messageCount) messageCount.textContent = '0';
        });
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            try {
                await fetch(`/agent/history/${currentSessionId}`, {
                    method: 'DELETE'
                });
                // Clear current conversation display
                if (transcriptionResult) transcriptionResult.classList.add('hidden');
                if (messageCount) messageCount.textContent = '0';
            } catch (error) {
                console.error('Failed to clear history:', error);
            }
        });
    }

    // Sessions modal handlers
    if (viewSessionsBtn) {
        viewSessionsBtn.addEventListener('click', async () => {
            await loadAndShowSessions();
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            sessionsModal.classList.add('hidden');
        });
    }

    if (sessionsModal) {
        sessionsModal.addEventListener('click', (e) => {
            if (e.target === sessionsModal) {
                sessionsModal.classList.add('hidden');
            }
        });
    }

    // Load and display all sessions
    async function loadAndShowSessions() {
        try {
            sessionsModal.classList.remove('hidden');
            sessionsList.innerHTML = 'Loading sessions...';

            const response = await fetch('/agent/sessions');
            const data = await response.json();

            if (data.sessions && data.sessions.length > 0) {
                let sessionsHtml = '';
                data.sessions.forEach(session => {
                    const isCurrentSession = session.session_id === currentSessionId;
                    const createdDate = new Date(session.created_at).toLocaleDateString();
                    const updatedDate = new Date(session.updated_at).toLocaleDateString();
                    
                    sessionsHtml += `
                        <div class="session-item ${isCurrentSession ? 'current' : ''}" data-session-id="${session.session_id}">
                            <h4>${session.session_id}</h4>
                            <div class="session-stats">
                                <span>Messages: ${session.message_count}</span>
                                <span>Created: ${createdDate}</span>
                            </div>
                            ${isCurrentSession ? '<p style="color: #6366f1; font-weight: 600; margin-top: 5px;">Current Session</p>' : ''}
                        </div>
                    `;
                });
                sessionsList.innerHTML = sessionsHtml;

                // Add click handlers to session items
                document.querySelectorAll('.session-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const sessionId = item.getAttribute('data-session-id');
                        if (sessionId !== currentSessionId) {
                            currentSessionId = sessionId;
                            updateSessionDisplay();
                            // Clear current conversation display
                            if (transcriptionResult) transcriptionResult.classList.add('hidden');
                            if (messageCount) messageCount.textContent = '0';
                            sessionsModal.classList.add('hidden');
                        }
                    });
                });
            } else {
                sessionsList.innerHTML = '<div class="no-sessions">No chat sessions found.<br/>Start a conversation to create your first session!</div>';
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            sessionsList.innerHTML = '<div class="no-sessions">Failed to load sessions. Please try again.</div>';
        }
    }

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
        } else if (currentMode === 'llm') {
            if (recordingText) recordingText.textContent = 'Recording your question...';
            if (processingText) processingText.textContent = 'AI is thinking and preparing response...';
            if (resultTitle) resultTitle.textContent = 'Your Question:';
        } else if (currentMode === 'chat') {
            if (recordingText) recordingText.textContent = 'Recording your message...';
            if (processingText) processingText.textContent = 'AI is thinking with conversation context...';
            if (resultTitle) resultTitle.textContent = 'Your Message:';
        }
    }

    // Check if elements exist before adding event listeners
    if (startRecordingBtn && stopRecordingBtn && audioPlayback && recordingIndicator) {
        startRecordingBtn.addEventListener('click', async () => {
            try {
                // Check if browser supports media recording
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error('Your browser does not support audio recording. Please use a modern browser like Chrome, Firefox, or Safari.');
                }

                // Request microphone access with timeout
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Microphone access request timed out')), 10000)
                );
                
                const streamPromise = navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        sampleRate: 44100
                    }
                });
                
                const stream = await Promise.race([streamPromise, timeoutPromise]);
                
                // Check if MediaRecorder is supported
                if (!MediaRecorder.isTypeSupported('audio/webm') && !MediaRecorder.isTypeSupported('audio/wav')) {
                    throw new Error('Your browser does not support audio recording formats.');
                }
                
                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/wav'
                });
                
                mediaRecorder.ondataavailable = event => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                mediaRecorder.onstop = async () => {
                    // Stop all tracks to release microphone
                    stream.getTracks().forEach(track => track.stop());
                    
                    if (audioChunks.length === 0) {
                        showError('No audio data recorded. Please try again.');
                        resetRecordingButtons();
                        return;
                    }
                    
                    audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    audioChunks = [];
                    
                    // Check if audio blob is too small (likely no audio)
                    if (audioBlob.size < 1000) {
                        showError('Recording seems too short or empty. Please speak closer to your microphone.');
                        resetRecordingButtons();
                        return;
                    }
                    
                    resetRecordingButtons();
                    
                    // Process the audio based on current mode
                    try {
                        if (currentMode === 'echo') {
                            await processEchoAudio();
                        } else if (currentMode === 'llm') {
                            await processLLMAudio();
                        } else if (currentMode === 'chat') {
                            await processChatAudio();
                        }
                    } catch (processError) {
                        console.error('Audio processing error:', processError);
                        showError('Failed to process your audio. Please try again.');
                    }
                };
                
                mediaRecorder.onerror = (event) => {
                    console.error('MediaRecorder error:', event.error);
                    showError('Recording error: ' + event.error.message);
                    resetRecordingButtons();
                };
                
                mediaRecorder.start();
                startRecordingBtn.disabled = true;
                stopRecordingBtn.disabled = false;
                recordingIndicator.classList.remove('hidden');
                audioPlayback.classList.add('hidden');
                if (transcribeContainer) transcribeContainer.classList.add('hidden');
                if (transcriptionResult) transcriptionResult.classList.add('hidden');
                
            } catch (err) {
                console.error('Recording start error:', err);
                let errorMessage = 'Could not start recording.';
                
                if (err.name === 'NotAllowedError' || err.message.includes('Permission denied')) {
                    errorMessage = 'Microphone access denied. Please allow microphone access in your browser settings and try again.';
                } else if (err.name === 'NotFoundError') {
                    errorMessage = 'No microphone found. Please connect a microphone and try again.';
                } else if (err.name === 'NotSupportedError') {
                    errorMessage = 'Your browser does not support audio recording. Please use Chrome, Firefox, or Safari.';
                } else if (err.message.includes('timeout')) {
                    errorMessage = 'Microphone access request timed out. Please try again and allow microphone access when prompted.';
                } else {
                    errorMessage = err.message || 'Could not start recording. Please check your microphone and try again.';
                }
                
                showError(errorMessage);
                resetRecordingButtons();
            }
        });

        stopRecordingBtn.addEventListener('click', () => {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        });
        
        function resetRecordingButtons() {
            stopRecordingBtn.disabled = true;
            startRecordingBtn.disabled = false;
            recordingIndicator.classList.add('hidden');
        }

        // Enhanced function to process echo audio with comprehensive error handling
        async function processEchoAudio() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            // Show processing status
            if (processingIndicator) processingIndicator.classList.remove('hidden');
            if (transcribeContainer) transcribeContainer.classList.remove('hidden');

            try {
                // Set timeout for the request
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
                
                const response = await fetch('/tts/echo', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                const data = await response.json();

                if (response.ok) {
                    // Handle successful responses
                    if (data.status === 'success') {
                        displaySuccessfulResult(data, 'echo');
                    } else if (data.status === 'partial_success') {
                        displayPartialResult(data, 'echo');
                    } else {
                        displayFallbackResult(data, 'echo');
                    }
                } else {
                    // Handle HTTP error responses
                    handleAPIError(data, response.status);
                }
            } catch (err) {
                handleNetworkError(err, 'echo processing');
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
                    if (chatInfo) chatInfo.classList.add('hidden'); // Hide chat info in LLM mode
                    
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

        // Enhanced function to process audio through chat pipeline with comprehensive error handling
        async function processChatAudio() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            // Show processing status
            if (processingIndicator) processingIndicator.classList.remove('hidden');
            if (transcribeContainer) transcribeContainer.classList.remove('hidden');

            try {
                // Set timeout for the request
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 second timeout for chat
                
                const response = await fetch(`/agent/chat/${currentSessionId}`, {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                const data = await response.json();

                if (response.ok) {
                    // Handle successful responses
                    if (data.status === 'success') {
                        displaySuccessfulResult(data, 'chat');
                        setupAutoRecording(data.audio_url);
                    } else if (data.status === 'partial_success') {
                        displayPartialResult(data, 'chat');
                    } else {
                        displayFallbackResult(data, 'chat');
                    }
                } else {
                    // Handle HTTP error responses
                    handleAPIError(data, response.status);
                }
            } catch (err) {
                handleNetworkError(err, 'chat processing');
            } finally {
                if (processingIndicator) processingIndicator.classList.add('hidden');
            }
        }
        
        function setupAutoRecording(audioUrl) {
            if (audioUrl && audioPlayback) {
                // Set up auto-recording after audio finishes
                audioPlayback.onended = () => {
                    console.log('Audio playback ended, starting auto-record in 1 second...');
                    setTimeout(() => {
                        if (currentMode === 'chat' && !startRecordingBtn.disabled) {
                            console.log('Auto-starting recording for next message...');
                            startRecordingBtn.click();
                        }
                    }, 1000); // 1 second delay after audio ends
                };
            }
        }

        // Keep the manual button for backup/re-processing
        if (transcribeBtn) {
            transcribeBtn.addEventListener('click', async () => {
                if (currentMode === 'echo') {
                    await processEchoAudio();
                } else if (currentMode === 'llm') {
                    await processLLMAudio();
                } else if (currentMode === 'chat') {
                    await processChatAudio();
                }
            });
        }
    }

    // Initialize UI for default mode and session
    initializeSession();
    updateUIForMode();
});

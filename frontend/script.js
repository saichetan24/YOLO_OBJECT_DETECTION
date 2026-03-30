// ========================================
// STATE MANAGEMENT
// ========================================
const AppState = {
    currentMode: 'home', // 'home', 'live', 'capture'
    cameraActive: false,
    detectionRunning: false,
    liveIntervalId: null,
    liveInFlight: false,
    mediaRecorder: null,
    recordedChunks: [],
    isRecording: false,
    recordingTimeout: null,
};

// ========================================
// DOM ELEMENTS
// ========================================
// Views
const homeView = document.getElementById('home-view');
const liveView = document.getElementById('live-view');
const captureView = document.getElementById('capture-view');

// Home buttons
const btnLiveMode = document.getElementById('btn-live-mode');
const btnCaptureMode = document.getElementById('btn-capture-mode');

// Live detection elements
const liveCamera = document.getElementById('camera');
const btnStartDetection = document.getElementById('btn-start-detection');
const btnStopDetection = document.getElementById('btn-stop-detection');
const btnBackFromLive = document.getElementById('btn-back-from-live');
const liveResult = document.getElementById('live-result');
const languageSelectLive = document.getElementById('language-select-live');

// Capture mode elements
const btnUploadPhoto = document.getElementById('btn-upload-photo');
const btnCapturePhoto = document.getElementById('btn-capture-photo');
const btnCaptureVideo = document.getElementById('btn-capture-video');
const btnStopRecording = document.getElementById('btn-stop-recording');
const btnBackFromCapture = document.getElementById('btn-back-from-capture');
const uploadInput = document.getElementById('upload-input');
const captureCamera = document.getElementById('capture-camera');
const captureVideoContainer = document.getElementById('capture-video-container');
const captureResult = document.getElementById('capture-result');
const timerDisplay = document.getElementById('timer-display');
const languageSelectCapture = document.getElementById('language-select-capture');

let timerInterval = null;
let selectedLanguage = 'en';

if (languageSelectLive && languageSelectCapture) {
    languageSelectLive.addEventListener('change', (e) => {
        selectedLanguage = e.target.value;
        languageSelectCapture.value = selectedLanguage;
    });

    languageSelectCapture.addEventListener('change', (e) => {
        selectedLanguage = e.target.value;
        languageSelectLive.value = selectedLanguage;
    });
}

// ========================================
// VIEW NAVIGATION
// ========================================
function showView(viewName) {
    // Hide all views
    homeView.classList.add('hidden');
    liveView.classList.add('hidden');
    captureView.classList.add('hidden');

    // Show requested view
    switch(viewName) {
        case 'home':
            homeView.classList.remove('hidden');
            AppState.currentMode = 'home';
            break;
        case 'live':
            liveView.classList.remove('hidden');
            AppState.currentMode = 'live';
            break;
        case 'capture':
            captureView.classList.remove('hidden');
            AppState.currentMode = 'capture';
            break;
    }
}

// ========================================
// CAMERA MANAGEMENT
// ========================================
async function startCamera(videoElement) {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 1280, height: 720 } 
        });
        videoElement.srcObject = stream;
        await videoElement.play();
        AppState.cameraActive = true;
        return true;
    } catch (err) {
        console.error('Camera error:', err);
        alert('Error accessing camera: ' + err.message);
        return false;
    }
}

function stopCamera(videoElement) {
    if (videoElement.srcObject) {
        const tracks = videoElement.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        videoElement.srcObject = null;
    }
    AppState.cameraActive = false;
}

// ========================================
// DETECTION HELPERS
// ========================================
function setStatus(element, message) {
    element.innerHTML = `<h2>${message}</h2>`;
}

function renderDetectionResult(element, data, isVideo = false) {
    const counts = data.counts || {};
    const entries = Object.entries(counts).map(([name, cnt]) => 
        cnt > 1 ? `${name} (${cnt})` : name
    );

    let html = '';
    if (entries.length > 0) {
        html += `<h2>✅ Detected: ${entries.join(', ')}</h2>`;
    } else {
        html += `<h2>❌ No Objects Detected</h2>`;
    }

    if (isVideo && typeof data.frames_processed === 'number') {
        html += `<p>📊 Frames processed: ${data.frames_processed}</p>`;
    }

    const navigation = data.navigation || null;
    if (navigation) {
        if (navigation.instruction) {
            html += `<h2>🧭 Guidance: ${navigation.instruction}</h2>`;
        }

        const zones = navigation.zones || {};
        html += `<p>Zones - Left: ${zones.left || 0}, Center: ${zones.center || 0}, Right: ${zones.right || 0}</p>`;

        if (Array.isArray(navigation.objects) && navigation.objects.length > 0) {
            const items = navigation.objects
                .slice(0, 6)
                .map(obj => `${obj.label} | ${obj.distance_m}m | ${obj.motion} | ${obj.zone}`);
            html += `<p>Objects: ${items.join(' | ')}</p>`;
        }
    }

    element.innerHTML = html;

    // Show annotated image
    if (data.annotated) {
        const img = document.createElement('img');
        img.src = data.annotated;
        img.className = 'annotated-image';
        element.appendChild(img);
    }

    // Show annotated frames for video
    if (Array.isArray(data.annotated_frames) && data.annotated_frames.length > 0) {
        const framesContainer = document.createElement('div');
        framesContainer.className = 'annotated-frames';

        data.annotated_frames.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            img.className = 'annotated-frame';
            framesContainer.appendChild(img);
        });

        element.appendChild(framesContainer);
    }
}

async function captureFrameBlob(videoElement) {
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth || 640;
    canvas.height = videoElement.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise(resolve => 
        canvas.toBlob(resolve, 'image/jpeg', 0.8)
    );
    if (!blob) throw new Error('Failed to create image blob');
    return blob;
}

async function sendFrameToEndpoint(videoElement, endpoint, extraFields = {}) {
    const blob = await captureFrameBlob(videoElement);
    const formData = new FormData();
    formData.append('frame', blob, 'frame.jpg');
    Object.entries(extraFields).forEach(([key, value]) => {
        formData.append(key, value);
    });

    const res = await fetch(endpoint, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Server error ${res.status}: ${txt}`);
    }

    return res.json();
}

// ========================================
// HOME VIEW - NAVIGATION
// ========================================
btnLiveMode.addEventListener('click', () => {
    showView('live');
});

btnCaptureMode.addEventListener('click', () => {
    showView('capture');
});

// ========================================
// LIVE DETECTION MODE
// ========================================
btnStartDetection.addEventListener('click', async () => {
    // Start camera first
    if (!AppState.cameraActive) {
        setStatus(liveResult, '📹 Starting camera...');
        const success = await startCamera(liveCamera);
        if (!success) {
            setStatus(liveResult, '❌ Failed to start camera');
            return;
        }
    }

    // Start detection loop
    btnStartDetection.disabled = true;
    btnStopDetection.disabled = false;
    btnBackFromLive.disabled = true;
    AppState.detectionRunning = true;
    setStatus(liveResult, '🔍 Live detection running...');

    AppState.liveIntervalId = setInterval(async () => {
        if (AppState.liveInFlight) return;
        AppState.liveInFlight = true;

        try {
            const data = await sendFrameToEndpoint(liveCamera, '/live-detect', { language: selectedLanguage });
            renderDetectionResult(liveResult, data, false);
        } catch (err) {
            console.error('Live detection error:', err);
            setStatus(liveResult, '❌ Detection error: ' + err.message);
        } finally {
            AppState.liveInFlight = false;
        }
    }, 500);
});

btnStopDetection.addEventListener('click', () => {
    // Stop detection loop
    if (AppState.liveIntervalId) {
        clearInterval(AppState.liveIntervalId);
        AppState.liveIntervalId = null;
    }

    AppState.detectionRunning = false;
    btnStartDetection.disabled = false;
    btnStopDetection.disabled = true;
    btnBackFromLive.disabled = false;
    setStatus(liveResult, '⏸️ Detection stopped');
});

btnBackFromLive.addEventListener('click', () => {
    // Stop detection if running
    if (AppState.liveIntervalId) {
        clearInterval(AppState.liveIntervalId);
        AppState.liveIntervalId = null;
    }

    // Stop camera
    stopCamera(liveCamera);

    // Reset state
    AppState.detectionRunning = false;
    btnStartDetection.disabled = false;
    btnStopDetection.disabled = true;
    btnBackFromLive.disabled = false;
    liveResult.innerHTML = '';

    // Go home
    showView('home');
});

// ========================================
// CAPTURE MODE - UPLOAD PHOTO
// ========================================
btnUploadPhoto.addEventListener('click', () => {
    uploadInput.click();
});

uploadInput.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    btnUploadPhoto.disabled = true;
    setStatus(captureResult, '📤 Uploading and analyzing...');

    try {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('language', selectedLanguage);

        const res = await fetch('/upload-image', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const txt = await res.text();
            throw new Error(`Server error ${res.status}: ${txt}`);
        }

        const data = await res.json();
        renderDetectionResult(captureResult, data, false);
    } catch (err) {
        console.error('Upload error:', err);
        setStatus(captureResult, '❌ Upload error: ' + err.message);
    } finally {
        btnUploadPhoto.disabled = false;
        uploadInput.value = '';
    }
});

// ========================================
// CAPTURE MODE - CAPTURE PHOTO
// ========================================
btnCapturePhoto.addEventListener('click', async () => {
    // Start camera if not active
    if (!AppState.cameraActive) {
        captureVideoContainer.classList.remove('hidden');
        setStatus(captureResult, '📹 Starting camera...');
        const success = await startCamera(captureCamera);
        if (!success) {
            setStatus(captureResult, '❌ Failed to start camera');
            captureVideoContainer.classList.add('hidden');
            return;
        }
        // Wait a moment for camera to initialize
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    btnCapturePhoto.disabled = true;
    setStatus(captureResult, '📸 Capturing and analyzing...');

    try {
        const data = await sendFrameToEndpoint(captureCamera, '/capture-image', { language: selectedLanguage });
        renderDetectionResult(captureResult, data, false);
        
        // Stop camera after capture
        stopCamera(captureCamera);
        captureVideoContainer.classList.add('hidden');
    } catch (err) {
        console.error('Capture error:', err);
        setStatus(captureResult, '❌ Capture error: ' + err.message);
    } finally {
        btnCapturePhoto.disabled = false;
    }
});

// ========================================
// CAPTURE MODE - CAPTURE VIDEO (30s)
// ========================================
btnCaptureVideo.addEventListener('click', async () => {
    if (AppState.isRecording) return;

    // Start camera if not active
    if (!AppState.cameraActive) {
        captureVideoContainer.classList.remove('hidden');
        setStatus(captureResult, '📹 Starting camera...');
        const success = await startCamera(captureCamera);
        if (!success) {
            setStatus(captureResult, '❌ Failed to start camera');
            captureVideoContainer.classList.add('hidden');
            return;
        }
        // Wait for camera to initialize
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    if (!window.MediaRecorder) {
        setStatus(captureResult, '❌ MediaRecorder not supported');
        return;
    }

    try {
        AppState.isRecording = true;
        AppState.recordedChunks = [];

        // Create MediaRecorder
        try {
            AppState.mediaRecorder = new MediaRecorder(captureCamera.srcObject, {
                mimeType: 'video/webm; codecs=vp8',
            });
        } catch (e) {
            AppState.mediaRecorder = new MediaRecorder(captureCamera.srcObject);
        }

        AppState.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                AppState.recordedChunks.push(event.data);
            }
        };

        AppState.mediaRecorder.onstop = async () => {
            const blob = new Blob(AppState.recordedChunks, { type: 'video/webm' });

            btnCaptureVideo.disabled = true;
            setStatus(captureResult, '📤 Uploading and analyzing video...');

            try {
                const formData = new FormData();
                formData.append('video', blob, 'capture.webm');
                formData.append('language', selectedLanguage);

                const res = await fetch('/capture-video', {
                    method: 'POST',
                    body: formData,
                });

                if (!res.ok) {
                    const txt = await res.text();
                    throw new Error(`Server error ${res.status}: ${txt}`);
                }

                const data = await res.json();
                renderDetectionResult(captureResult, data, true);
                
                // Stop camera after video processing
                stopCamera(captureCamera);
                captureVideoContainer.classList.add('hidden');
            } catch (err) {
                console.error('Video upload error:', err);
                setStatus(captureResult, '❌ Video error: ' + err.message);
            } finally {
                btnCaptureVideo.disabled = false;
                btnCaptureVideo.classList.remove('hidden');
                btnStopRecording.classList.add('hidden');
                AppState.isRecording = false;
            }
        };

        btnCaptureVideo.classList.add('hidden');
        btnStopRecording.classList.remove('hidden');
        setStatus(captureResult, '🎥 Recording video... (Click Stop to finish early)');

        // Show and start countdown timer
        timerDisplay.classList.remove('hidden');
        let timeRemaining = 30;
        timerDisplay.textContent = timeRemaining;

        AppState.mediaRecorder.start();

        // Update timer every second
        timerInterval = setInterval(() => {
            timeRemaining--;
            timerDisplay.textContent = timeRemaining;
            if (timeRemaining <= 0) {
                clearInterval(timerInterval);
            }
        }, 1000);

        // Auto-stop after 30 seconds
        AppState.recordingTimeout = setTimeout(() => {
            if (AppState.mediaRecorder && AppState.mediaRecorder.state !== 'inactive') {
                AppState.mediaRecorder.stop();
            }
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            timerDisplay.classList.add('hidden');
        }, 30000);

    } catch (err) {
        console.error('Recording error:', err);
        setStatus(captureResult, '❌ Recording failed: ' + err.message);
        AppState.isRecording = false;
        btnCaptureVideo.disabled = false;
        btnCaptureVideo.classList.remove('hidden');
        btnStopRecording.classList.add('hidden');
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        if (AppState.recordingTimeout) {
            clearTimeout(AppState.recordingTimeout);
            AppState.recordingTimeout = null;
        }
        timerDisplay.classList.add('hidden');
    }
});

// ========================================
// CAPTURE MODE - STOP RECORDING BUTTON
// ========================================
btnStopRecording.addEventListener('click', () => {
    if (AppState.mediaRecorder && AppState.mediaRecorder.state !== 'inactive') {
        // Clear the auto-stop timeout
        if (AppState.recordingTimeout) {
            clearTimeout(AppState.recordingTimeout);
            AppState.recordingTimeout = null;
        }
        
        // Clear timer interval
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        
        // Hide timer
        timerDisplay.classList.add('hidden');
        
        // Stop recording
        AppState.mediaRecorder.stop();
    }
});

// ========================================
// CAPTURE MODE - BACK BUTTON
// ========================================
btnBackFromCapture.addEventListener('click', () => {
    // Stop camera if running
    if (AppState.cameraActive) {
        stopCamera(captureCamera);
    }

    // Hide video container
    captureVideoContainer.classList.add('hidden');

    // Reset recording state
    if (AppState.mediaRecorder && AppState.mediaRecorder.state !== 'inactive') {
        AppState.mediaRecorder.stop();
    }
    AppState.isRecording = false;

    // Clear recording timeout
    if (AppState.recordingTimeout) {
        clearTimeout(AppState.recordingTimeout);
        AppState.recordingTimeout = null;
    }

    // Reset UI
    btnCaptureVideo.disabled = false;
    btnCaptureVideo.classList.remove('hidden');
    btnStopRecording.classList.add('hidden');
    captureResult.innerHTML = '';
    
    // Clear timer if running
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    timerDisplay.classList.add('hidden');

    // Go home
    showView('home');
});

// ========================================
// INITIALIZATION
// ========================================
// Start on home view (camera NOT started)
showView('home');
console.log('✅ Blind Assistance System loaded - Camera will start on demand');

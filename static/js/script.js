document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('video');
    const overlay = document.getElementById('overlay');
    const captureBtn = document.getElementById('capture-btn');
    const feedback = document.getElementById('feedback');
    const selectedEyeText = document.getElementById('selected-eye');
    const capturedImage = document.getElementById('captured-image');
    const saveImageBtn = document.getElementById('save-image-btn');
    const darkModeToggle = document.getElementById('darkModeToggle');
    
    const confirmationModalElement = document.getElementById('confirmationModal');
    const confirmationModal = new bootstrap.Modal(confirmationModalElement);
    
    const toastElement = document.getElementById('toast');
    const toast = new bootstrap.Toast(toastElement);
    
    let selectedEye = 'left';
    
    const eyeOptionRadios = document.getElementsByName('eyeOptions');
    eyeOptionRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
            selectedEye = event.target.value;
            selectedEyeText.textContent = selectedEye;
        });
    });
    
    const faceMesh = new FaceMesh({
        locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
        }
    });
    
    faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.7,
        minTrackingConfidence: 0.5
    });
    
    const canvasCtx = overlay.getContext('2d');
    
    const FACEMESH_LEFT_EYE = [33, 133, 160, 159, 158, 157, 173, 144, 145, 153, 154, 155, 133];
    const FACEMESH_RIGHT_EYE = [362, 263, 387, 386, 385, 384, 398, 373, 374, 380, 381, 382, 263];
    
    let isEyeCentered = false;
    let isEyeBlinking = false;
    
    let eyeBoundingBox = {
        xMin: 0,
        yMin: 0,
        width: 0,
        height: 0
    };
    
    const EAR_THRESHOLD = 0.25; 
    let blinkCounter = 0;
    let blinkLimit = 1;
    
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        darkModeToggle.checked = true;
    }

    darkModeToggle.addEventListener('change', () => {
        if (darkModeToggle.checked) {
            document.body.classList.add('dark-mode');
            localStorage.setItem('darkMode', 'enabled');
        } else {
            document.body.classList.remove('dark-mode');
            localStorage.setItem('darkMode', 'disabled');
        }
    });
    
    const initializeCamera = (width = 480, height = 360) => {
        camera.stop(); 
        camera.start({
            width: width,
            height: height
        });
        video.width = width;
        video.height = height;
        overlay.width = width;
        overlay.height = height;
        eyeBoundingBox = {xMin: 0, yMin: 0, width: 0, height: 0};
        canvasCtx.clearRect(0, 0, overlay.width, overlay.height);
    };
    
    const camera = new Camera(video, {
        onFrame: async () => {
            try {
                await faceMesh.send({ image: video });
            } catch (error) {
                console.error('Error sending frame to FaceMesh:', error);
            }
        },
        width: 480,
        height: 360
    });
    camera.start();
    
    faceMesh.onResults(results => {
        canvasCtx.save();
        canvasCtx.clearRect(0, 0, overlay.width, overlay.height);
    
        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
            const landmarks = results.multiFaceLandmarks[0];
            const eyeIndices = selectedEye === 'left' ? FACEMESH_LEFT_EYE : FACEMESH_RIGHT_EYE;
            
            const eyeLandmarks = eyeIndices.map(index => landmarks[index]);

            let EAR = 0;
            if (selectedEye === 'left') {
                const top = landmarks[159];
                const bottom = landmarks[145];
                const left = landmarks[33];
                const right = landmarks[133];
                const vertical = Math.hypot(top.x - bottom.x, top.y - bottom.y);
                const horizontal = Math.hypot(left.x - right.x, left.y - right.y);
                EAR = vertical / horizontal;
            } else {
                const top = landmarks[386];
                const bottom = landmarks[374];
                const left = landmarks[362];
                const right = landmarks[263];
                const vertical = Math.hypot(top.x - bottom.x, top.y - bottom.y);
                const horizontal = Math.hypot(left.x - right.x, left.y - right.y);
                EAR = vertical / horizontal;
            }

            if (EAR < EAR_THRESHOLD) {
                blinkCounter += 1;
                if (blinkCounter >= blinkLimit) {
                    if (!isEyeBlinking) {
                        isEyeBlinking = true;
                        isEyeCentered = false;
                        captureBtn.disabled = true;
                        captureBtn.classList.remove('btn-success');
                        captureBtn.classList.add('btn-secondary');
                        toastElement.querySelector('.toast-body').textContent = 'Please keep your eye open to capture.';
                        toastElement.classList.remove('text-bg-success', 'text-bg-primary', 'text-bg-warning');
                        toastElement.classList.add('text-bg-warning');
                        toast.show();
                    }
                }
            } else {
                if (blinkCounter >= blinkLimit) {
                    if (isEyeBlinking) { // Prevent multiple toasts
                        isEyeBlinking = false;
                        toastElement.querySelector('.toast-body').textContent = 'Eye is open. You can capture now.';
                        toastElement.classList.remove('text-bg-warning', 'text-bg-danger');
                        toastElement.classList.add('text-bg-success');
                        toast.show();
                    }
                }
                blinkCounter = 0;
            }

            const xCoords = eyeLandmarks.map(lm => lm.x * overlay.width);
            const yCoords = eyeLandmarks.map(lm => lm.y * overlay.height);
            const xMin = Math.min(...xCoords);
            const xMax = Math.max(...xCoords);
            const yMin = Math.min(...yCoords);
            const yMax = Math.max(...yCoords);
            const width = xMax - xMin;
            const height = yMax - yMin;

            // Update eye bounding box
            eyeBoundingBox = {
                xMin: xMin,
                yMin: yMin,
                width: width,
                height: height
            };

            const FACEMESH_EYE_CONNECTIONS = selectedEye === 'left' ? FACEMESH_LEFT_EYE : FACEMESH_RIGHT_EYE;
            drawConnectors(canvasCtx, landmarks, FACEMESH_EYE_CONNECTIONS, {color: '#00c853', lineWidth: 1});
            drawLandmarks(canvasCtx, landmarks, {color: '#ff0000', lineWidth: 1});

            const alignmentBox = {
                xMin: overlay.width * 0.25,
                xMax: overlay.width * 0.75,
                yMin: overlay.height * 0.2,
                yMax: overlay.height * 0.8
            };

            if (
                xMin > alignmentBox.xMin && 
                (xMax < alignmentBox.xMax) && 
                yMin > alignmentBox.yMin && 
                (yMax < alignmentBox.yMax) &&
                !isEyeBlinking
            ) {
                // Eye is properly aligned
                if (!isEyeCentered) { // Prevent multiple toasts
                    isEyeCentered = true;
                    captureBtn.disabled = false;
                    captureBtn.classList.remove('btn-secondary');
                    captureBtn.classList.add('btn-success');
                    // Inform user that capture is enabled
                    toastElement.querySelector('.toast-body').textContent = 'Eye is properly aligned. You can capture now.';
                    toastElement.classList.remove('text-bg-warning', 'text-bg-danger');
                    toastElement.classList.add('text-bg-primary');
                    toast.show();
                }
            } else {
                // Eye not properly aligned
                if (isEyeCentered) { // Prevent multiple toasts
                    isEyeCentered = false;
                    captureBtn.disabled = true;
                    captureBtn.classList.remove('btn-success');
                    captureBtn.classList.add('btn-secondary');
                    // Inform user to align eye
                    toastElement.querySelector('.toast-body').textContent = 'Please align your eye within the box.';
                    toastElement.classList.remove('text-bg-success', 'text-bg-primary');
                    toastElement.classList.add('text-bg-warning');
                    toast.show();
                }
            }

            // Draw bounding rectangle around the eye
            canvasCtx.strokeStyle = isEyeCentered ? '#00c853' : '#ff0000';
            canvasCtx.lineWidth = 2;
            canvasCtx.strokeRect(xMin - 10, yMin - 10, width + 20, height + 20);
        }

        canvasCtx.restore();
    });
    
    // Capture Button Event
    captureBtn.addEventListener('click', () => {
        if (!isEyeCentered) return;

        captureBtn.disabled = true;
        captureBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Capturing...';

        // Notify user that capturing has started
        toastElement.querySelector('.toast-body').textContent = 'Capturing eye image...';
        toastElement.classList.remove('text-bg-success', 'text-bg-danger', 'text-bg-warning');
        toastElement.classList.add('text-bg-primary');
        toast.show();

        // Capture the current frame
        const captureCanvas = document.createElement('canvas');
        captureCanvas.width = video.videoWidth;
        captureCanvas.height = video.videoHeight;
        const captureCtx = captureCanvas.getContext('2d');
        captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);

        // Ensure bounding box is within the video frame
        const x = Math.max(0, eyeBoundingBox.xMin - 10);
        const y = Math.max(0, eyeBoundingBox.yMin - 10);
        const cropWidth = Math.min(eyeBoundingBox.width + 20, captureCanvas.width - x);
        const cropHeight = Math.min(eyeBoundingBox.height + 20, captureCanvas.height - y);

        // Validate crop dimensions
        if (cropWidth <= 0 || cropHeight <= 0) {
            toastElement.querySelector('.toast-body').textContent = 'Invalid capture area. Please adjust your position.';
            toastElement.classList.remove('text-bg-primary');
            toastElement.classList.add('text-bg-danger');
            toast.show();
            captureBtn.disabled = false;
            captureBtn.innerHTML = '<i class="fas fa-camera"></i> Capture';
            return;
        }

        // Crop the eye region
        const croppedEyeCanvas = document.createElement('canvas');
        croppedEyeCanvas.width = cropWidth;
        croppedEyeCanvas.height = cropHeight;
        const croppedCtx = croppedEyeCanvas.getContext('2d');
        // Removed image filters to preserve quality
        croppedCtx.drawImage(
            captureCanvas,
            x,
            y,
            cropWidth,
            cropHeight,
            0,
            0,
            cropWidth,
            cropHeight
        );

        const imageDataURL = croppedEyeCanvas.toDataURL('image/png');

        // Show in modal
        capturedImage.src = imageDataURL;
        confirmationModal.show();

        // Reset capture button and notify completion
        captureBtn.innerHTML = '<i class="fas fa-camera"></i> Capture';
        toastElement.querySelector('.toast-body').textContent = 'Eye image captured successfully.';
        toastElement.classList.remove('text-bg-primary');
        toastElement.classList.add('text-bg-success');
        toast.show();
    });
    
// static/js/script.js

// ... [existing code] ...

// Save Image Button Event
saveImageBtn.addEventListener('click', () => {
    const imageSrc = capturedImage.src;

    fetch('/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageSrc, eye: selectedEye })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update toast content
            toastElement.querySelector('.toast-body').textContent = data.message;
            toastElement.classList.remove('text-bg-danger', 'text-bg-primary', 'text-bg-warning');
            toastElement.classList.add('text-bg-success');
            toast.show();
            feedback.innerHTML = `
                <div class="alert alert-success mt-2">
                    ${data.message}<br>
                    Filename: ${data.filename}<br>
                    Iris Radius: ${data.iris_radius ? data.iris_radius + ' px' : 'N/A'}<br>
                    Pupil Diameter: ${data.pupil_diameter ? data.pupil_diameter + ' px' : 'N/A'}
                </div>
            `;
        } else {
            // Update toast for error
            toastElement.querySelector('.toast-body').textContent = data.message;
            toastElement.classList.remove('text-bg-success', 'text-bg-primary', 'text-bg-warning');
            toastElement.classList.add('text-bg-danger');
            toast.show();
            feedback.innerHTML = `<div class="alert alert-danger mt-2">${data.message}</div>`;
        }
    })
    .catch(error => {
        toastElement.querySelector('.toast-body').textContent = `Error: ${error}`;
        toastElement.classList.remove('text-bg-success', 'text-bg-primary', 'text-bg-warning');
        toastElement.classList.add('text-bg-danger');
        toast.show();
        feedback.innerHTML = `<div class="alert alert-danger mt-2">Error: ${error}</div>`;
    })
    .finally(() => {
        confirmationModal.hide();
        captureBtn.disabled = false;
    });
});



    // Handle Share Button Click in Images Gallery
    const shareButtons = document.querySelectorAll('.share-btn');
    const shareModal = new bootstrap.Modal(document.getElementById('shareModal'));
    let currentFilename = '';

    shareButtons.forEach(button => {
        button.addEventListener('click', () => {
            currentFilename = button.getAttribute('data-filename');
            shareModal.show();
        });
    });

    // Handle Share Form Submission
    const shareForm = document.getElementById('shareForm');
    if (shareForm) {
        shareForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = document.getElementById('recipientEmail').value;

            fetch(`/share/${currentFilename}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ email: email })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success toast
                    toastElement.querySelector('.toast-body').textContent = data.message;
                    toastElement.classList.remove('text-bg-danger', 'text-bg-primary', 'text-bg-warning');
                    toastElement.classList.add('text-bg-success');
                    toast.show();
                    shareModal.hide();
                } else {
                    // Show error toast
                    toastElement.querySelector('.toast-body').textContent = data.message;
                    toastElement.classList.remove('text-bg-success', 'text-bg-primary', 'text-bg-warning');
                    toastElement.classList.add('text-bg-danger');
                    toast.show();
                }
            })
            .catch(error => {
                // Show error toast
                toastElement.querySelector('.toast-body').textContent = `Error: ${error}`;
                toastElement.classList.remove('text-bg-success', 'text-bg-primary', 'text-bg-warning');
                toastElement.classList.add('text-bg-danger');
                toast.show();
            });
        });
    }

    // Lazy Loading for Images Gallery
    const lazyImages = document.querySelectorAll('img.lazy');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });

    lazyImages.forEach(img => {
        imageObserver.observe(img);
    });
});

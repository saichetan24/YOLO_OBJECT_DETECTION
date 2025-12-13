# Real-Time Object Detection & Voice Assistance

This project demonstrates a simple real-time object detection backend (YOLO via ultralytics) with a JavaScript frontend capturing webcam frames and a voice assistant announcing detected objects.

IMPORTANT: this project requires Python 3.10. The developer has tested the specified pinned library versions on Python 3.10.

## Project structure

RealTime_Object_Detection/
├── backend/
│   ├── app.py
│   ├── best.pt
│   ├── requirements.txt
   │   ├── uploads/
│   └── utils/
│       ├── detect.py
│       └── voice.py
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js

## Setup (Windows / PowerShell)

1. Install Python 3.10 and ensure `python3.10` or `py -3.10` is available.
2. Create and activate the venv from the project root:

```powershell
python3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install exact pinned requirements:

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

4. Run the backend (development):

```powershell
python backend\app.py
```

5. Open `frontend/index.html` in Chrome (file:///) or serve it from a static server. The frontend will POST frames to `http://localhost:5000/detect`.

## Notes & Troubleshooting
- The pinned library versions in `backend/requirements.txt` are chosen for compatibility with Python 3.10. Using Python 3.13 or 3.11 may result in binary incompatibilities for `torch`, `opencv-python`, and other native extensions.
- If you see import errors after installing requirements, ensure your active interpreter is the venv's Python (activate the venv before running `python`).
- Voice uses `pyttsx3` and runs in a background thread; make sure your machine has an audio output device.

## API

POST /detect
- form field `frame`: image file (jpeg)
- response: JSON `{ "detected": ["person", "bottle"] }`
# Real-Time Object Detection and Voice Assistant

This project uses YOLO + OpenCV + Python to detect objects in real-time and speak them aloud.

## Folder Structure

RealTime_Object_Detection/
├── best.pt
├── main.py
├── detect_image.py
├── detect_video.py
├── requirements.txt
└── assets/

## Setup

pip install -r requirements.txt

## Run Real-Time Detection
python main.py

## Detect on Image
python detect_image.py

## Detect on Video
python detect_video.py

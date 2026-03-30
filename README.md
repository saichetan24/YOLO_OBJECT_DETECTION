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

# Real-Time Object Detection & Voice Assistant

This repository implements a web-enabled real-time object detection system using a trained YOLO model (`best.pt`), a Flask backend that runs the detector and (optionally) speaks results, and a small JavaScript frontend that captures webcam frames and sends them to the API.

Summary
- Backend: `backend/app.py` exposes `/detect` (POST) and serves the frontend files.
- Detection: `backend/utils/detect.py` loads `best.pt` once and returns detected class names.
- Voice: `backend/utils/voice.py` uses `pyttsx3` in a background worker (lazy init).
- Frontend: `frontend/index.html`, `frontend/script.js`, `frontend/style.css` — webcam capture, send frame, show results.

IMPORTANT: Use Python 3.10 for this project. The pinned binary packages (torch, opencv, ultralytics) are tested against Python 3.10.

Contents

RealTime_Object_Detection/
- backend/
    - app.py
    - best.pt
    - requirements.txt
    - uploads/    (runtime uploads; should be ignored in git)
    - utils/
        - detect.py
        - voice.py
- frontend/
    - index.html
    - script.js
    - style.css
- README.md

Prerequisites
- Windows with Python 3.10 installed (or any OS with Python 3.10).
- Optional: GPU and CUDA-compatible torch build if you want faster inference.

Setup (PowerShell)

1. From project root, create and activate the venv with Python 3.10:

```powershell
python3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Upgrade pip and install the exact pinned requirements:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend\requirements.txt
```

Notes about `playsound` and voice:
- `pyttsx3` is used for TTS and is the primary voice method in this project.
- `playsound==1.3.0` is included in `requirements.txt` but may fail to build on some platforms; it is optional.

Run the backend (development)

```powershell
python backend\app.py
```

This starts the Flask server on http://127.0.0.1:5000. The app will also serve the frontend files at `/` so you can open that URL in Chrome.

Open the frontend
- In Chrome, visit: http://localhost:5000/
- Allow the browser to access the webcam, then click "Capture & Detect". The frontend will POST the captured frame as `form-data` field `frame` to `POST /detect`.

API

POST /detect
- Content: multipart/form-data with field `frame` (image/jpeg)
- Response (JSON):

```json
{ "detected": ["person", "chair"] }
```

Example curl (from another machine):

```bash
curl -F "frame=@frame.jpg" http://localhost:5000/detect
```

What happens on a request
- The backend saves the uploaded file to `backend/uploads/`.
- `detect_image()` runs the ultralytics YOLO model on the saved file and returns detected class names.
- `speak_items()` enqueues the detected names to the pyttsx3 worker (if available).
- The API returns `{"detected": [...]}` to the caller.

Improvement: return annotated image URL
- The current API returns only class names. If you want annotated images returned, I can update `detect_image()` to save `results[0].plot()` output to `backend/uploads/annotated-<uuid>.jpg` and include an `annotated` URL in the JSON response.

Development notes & troubleshooting

- If the server logs show `Failed to initialize pyttsx3; voice disabled`, run the pywin32 postinstall (Windows) inside the activated venv to enable SAPI5:

```powershell
python -m pip install pywin32
python -m pywin32_postinstall -install
```

- If some packages fail to install on your Python version, ensure you are running Python 3.10 inside the activated venv.
- To speed up inference, resize frames on the frontend before sending them or enable CUDA (requires a GPU and matching torch build).

Git / repository notes

- The `backend/uploads/` directory contains runtime images and should not be committed. Add the following `.gitignore` to the project root if not present:

```
/.venv/
/backend/uploads/
__pycache__/
*.pyc
```

- To remove already committed uploads from the remote repository use:

```powershell
git rm -r --cached backend/uploads
git commit -m "Remove uploads from repo"
git push
```

Additional help
- Want annotated images in responses? Say: "add annotated images to API"
- Want me to add `.gitignore` and remove uploads from repo history? Say: "clean repo uploads"
- Want voice enabled and tested? Say: "enable voice" and I will run the pywin32 postinstall and restart the server.

Blind Navigation Assistant (real-time)
- A standalone advanced assistive script is available at `backend/blind_navigation_assistant.py`.
- Features include frame zoning (left/center/right), distance estimation in meters, static vs moving object classification, multilingual guidance (`en`, `hi`, `te`), smart speech cooldown, and visual overlays.

Run (PowerShell):

```powershell
python backend\blind_navigation_assistant.py --model yolov8n.pt --language en --conf 0.35 --frame-skip 1
```

Controls:
- Press `1` for English, `2` for Hindi, `3` for Telugu, `q` to quit.
- If webcam index 0 fails, try `--camera 1`.

License & attribution
- This repo contains your trained model `best.pt`. Keep licensing and distribution of that model in mind.

---
Updated: December 13, 2025

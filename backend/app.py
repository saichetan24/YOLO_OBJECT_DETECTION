import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory

from utils.detect import detect_image, detect_video
from utils.voice import speak_items, speak_text

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


@app.after_request
def add_cors_headers(response):
    # Allow local frontend to access API during development
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def _build_detection_response(counts, annotated_data=None, navigation=None):
    """Standard JSON response for all detection endpoints.

    ``annotated_data`` is an optional data URL (base64-encoded image).
    """
    detected_classes = sorted(counts.keys()) if counts else []
    resp = {
        "detected": detected_classes,
        "counts": counts,
    }
    if annotated_data:
        resp["annotated"] = annotated_data
    if navigation:
        resp["navigation"] = navigation
    return resp


def _speak_counts(counts, avoid_repetition=False):
    """Speak a summary of detected objects using the voice module.
    
    Args:
        counts: Dictionary mapping object names to counts
        avoid_repetition: If True, only speak if objects have changed
    """
    try:
        speak_list = []
        for name, cnt in counts.items():
            if cnt == 1:
                speak_list.append(name)
            else:
                speak_list.append(f"{cnt} {name}s")
        if speak_list:
            logging.info(f"Speaking objects: {speak_list}")
            speak_items(speak_list, avoid_repetition=avoid_repetition)
    except Exception:
        logging.exception("Voice announcement failed (continuing)")


def _normalize_language(lang):
    if not lang:
        return "en"
    lang = str(lang).strip().lower()
    return lang if lang in {"en", "hi", "te"} else "en"


@app.route("/detect", methods=["POST"])
def detect_route():
    language = _normalize_language(request.form.get("language", "en"))

    if "frame" not in request.files:
        return jsonify({"error": "No file part 'frame' in the request"}), 400

    file = request.files["frame"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # Save file
    filename = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(save_path)
    except Exception as e:
        logging.exception("Failed to save uploaded file")
        return jsonify({"error": "Failed to save file", "detail": str(e)}), 500

    try:
        counts, annotated_name, navigation = detect_image(save_path, language=language)
    except Exception as e:
        logging.exception("Detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass

    # Optional voice announcement
    if navigation and navigation.get("instruction"):
        speak_text(navigation["instruction"], avoid_repetition=True)
    else:
        _speak_counts(counts)

    response = _build_detection_response(counts, annotated_name, navigation)
    return jsonify(response)


@app.route("/live-detect", methods=["POST"])
def live_detect_route():
    """Continuous live detection endpoint for streaming frames."""
    language = _normalize_language(request.form.get("language", "en"))
    if "frame" not in request.files:
        return jsonify({"error": "No file part 'frame' in the request"}), 400

    file = request.files["frame"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = f"live-{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(save_path)
    except Exception as e:
        logging.exception("Failed to save uploaded live frame")
        return jsonify({"error": "Failed to save file", "detail": str(e)}), 500

    try:
        counts, annotated_name, navigation = detect_image(save_path, language=language)
    except Exception as e:
        logging.exception("Live detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass

    # For live mode, speak instruction with repetition avoidance.
    if navigation and navigation.get("instruction"):
        speak_text(navigation["instruction"], avoid_repetition=True)
    else:
        _speak_counts(counts, avoid_repetition=True)
    
    response = _build_detection_response(counts, annotated_name, navigation)
    return jsonify(response)


@app.route("/capture-image", methods=["POST"])
def capture_image_route():
    """Capture a single photo from the webcam and analyze it."""
    language = _normalize_language(request.form.get("language", "en"))
    if "frame" not in request.files:
        return jsonify({"error": "No file part 'frame' in the request"}), 400

    file = request.files["frame"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = f"capture-{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(save_path)
    except Exception as e:
        logging.exception("Failed to save captured image")
        return jsonify({"error": "Failed to save file", "detail": str(e)}), 500

    try:
        counts, annotated_name, navigation = detect_image(save_path, language=language)
    except Exception as e:
        logging.exception("Capture-image detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass

    if navigation and navigation.get("instruction"):
        speak_text(navigation["instruction"], avoid_repetition=False)
    else:
        _speak_counts(counts)
    response = _build_detection_response(counts, annotated_name, navigation)
    return jsonify(response)


@app.route("/upload-image", methods=["POST"])
def upload_image_route():
    """Analyze a user-uploaded image file from disk."""
    language = _normalize_language(request.form.get("language", "en"))
    if "image" not in request.files:
        return jsonify({"error": "No file part 'image' in the request"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"upload-{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(save_path)
    except Exception as e:
        logging.exception("Failed to save uploaded image")
        return jsonify({"error": "Failed to save file", "detail": str(e)}), 500

    try:
        counts, annotated_name, navigation = detect_image(save_path, language=language)
    except Exception as e:
        logging.exception("Upload-image detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass

    if navigation and navigation.get("instruction"):
        speak_text(navigation["instruction"], avoid_repetition=False)
    else:
        _speak_counts(counts)
    response = _build_detection_response(counts, annotated_name, navigation)
    return jsonify(response)


@app.route("/capture-video", methods=["POST"])
def capture_video_route():
    """Accept a 30-second webcam recording and analyze it frame-by-frame."""
    if "video" not in request.files:
        return jsonify({"error": "No file part 'video' in the request"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1] or ".webm"
    filename = f"video-{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        file.save(save_path)
    except Exception as e:
        logging.exception("Failed to save uploaded video")
        return jsonify({"error": "Failed to save file", "detail": str(e)}), 500

    try:
        counts, annotated_frames, frames_processed = detect_video(save_path)
    except Exception as e:
        logging.exception("Video detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass

    _speak_counts(counts)

    response = _build_detection_response(counts)
    response["frames_processed"] = frames_processed
    if annotated_frames:
        # Frames are already data URLs; pass them through
        response["annotated_frames"] = annotated_frames

    return jsonify(response)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# Serve frontend files so opening http://localhost:5000/ shows the UI
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))


@app.route("/")
def index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return ("Frontend index not found. Make sure frontend/index.html exists."), 404
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route('/<path:filename>')
def frontend_static(filename):
    # Serve static files (css, js, assets) from the frontend folder
    file_path = os.path.join(FRONTEND_DIR, filename)
    if not os.path.exists(file_path):
        return ("Not Found", 404)
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Run the Flask app for development. Use .venv and Python 3.10 as instructed.
    app.run(host="0.0.0.0", port=5000, debug=True)

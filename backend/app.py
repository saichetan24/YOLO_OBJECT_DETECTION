import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory

from utils.detect import detect_image
from utils.voice import speak_items

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


@app.route("/detect", methods=["POST"])
def detect_route():
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
        counts, annotated_name = detect_image(save_path)
    except Exception as e:
        logging.exception("Detection failed")
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500

    # Trigger voice announcement (non-blocking) - speak keys with counts
    try:
        speak_list = []
        for name, cnt in counts.items():
            if cnt == 1:
                speak_list.append(name)
            else:
                speak_list.append(f"{cnt} {name}s")
        speak_items(speak_list)
    except Exception:
        logging.exception("Voice announcement failed (continuing)")

    response = {"detected": counts}
    if annotated_name:
        response["annotated"] = f"/uploads/{annotated_name}"

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

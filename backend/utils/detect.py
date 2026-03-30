import os
import threading
import base64
import math
import time
from ultralytics import YOLO
import numpy as np
import cv2

# Load model once at import time (lazy load)
_model = None
_model_lock = threading.Lock()


KNOWN_OBJECT_WIDTHS_M = {
    "person": 0.5,
    "chair": 0.5,
    "bottle": 0.07,
    "table": 1.2,
    "car": 1.8,
    "bicycle": 0.6,
    "motorcycle": 0.8,
    "dog": 0.25,
    "cat": 0.15,
}


TRANSLATIONS = {
    "en": {
        "path_clear": "Path clear. Move forward.",
        "move_left": "Obstacle on right. Move left.",
        "move_right": "Obstacle on left. Move right.",
        "center_stop": "Obstacle ahead. Stop or move left or right.",
        "moving_ahead_stop": "Moving object ahead at {dist} meters. Stop.",
        "very_close": "Very close obstacle ahead. Stop immediately.",
        "caution": "Obstacle ahead within {dist} meters. Proceed with caution.",
    },
    "hi": {
        "path_clear": "Samne rasta saaf hai, aage badhein.",
        "move_left": "Dahine taraf badha hai, baen taraf jayein.",
        "move_right": "Baen taraf badha hai, dahine taraf jayein.",
        "center_stop": "Samne badha hai, ruk jaiye ya baen/dahine jayein.",
        "moving_ahead_stop": "Chalta hua vastu samne {dist} meter par hai. Rukiye.",
        "very_close": "Bahut kareeb badha hai. Turant ruk jaiye.",
        "caution": "Samne badha {dist} meter par hai. Savdhani se chaleye.",
    },
    "te": {
        "path_clear": "Margam khaleega undi. Munduku vellandi.",
        "move_left": "Kudi vaipu addanki undi. Edama vaipu kadalandi.",
        "move_right": "Edama vaipu addanki undi. Kudi vaipu kadalandi.",
        "center_stop": "Mundu addanki undi. Agandi leka edama/kudi vaipu kadalandi.",
        "moving_ahead_stop": "Kadulutunna vastu mundu {dist} meetarla dooramlo undi. Agandi.",
        "very_close": "Chala daggaralo addanki undi. Ventane agandi.",
        "caution": "Mundu addanki {dist} meetarla dooramlo undi. Jagratthaga vellandi.",
    },
}


class _MotionTracker:
    def __init__(self, move_threshold_px=18.0, match_distance_px=110.0):
        self.move_threshold_px = move_threshold_px
        self.match_distance_px = match_distance_px
        self._tracks = {}
        self._next_id = 1

    @staticmethod
    def _distance(p1, p2):
        return math.hypot(float(p1[0] - p2[0]), float(p1[1] - p2[1]))

    def classify_motion(self, label, center):
        best_id = None
        best_dist = float("inf")

        for track_id, track in self._tracks.items():
            if track["label"] != label:
                continue
            d = self._distance(center, track["center"])
            if d < best_dist and d <= self.match_distance_px:
                best_id = track_id
                best_dist = d

        if best_id is None:
            tid = self._next_id
            self._next_id += 1
            self._tracks[tid] = {"label": label, "center": center, "last_seen": time.time()}
            return "static"

        prev_center = self._tracks[best_id]["center"]
        moved = self._distance(center, prev_center)
        self._tracks[best_id]["center"] = center
        self._tracks[best_id]["last_seen"] = time.time()
        return "moving" if moved >= self.move_threshold_px else "static"

    def prune(self, max_age_sec=1.5):
        now = time.time()
        stale_ids = [
            track_id
            for track_id, track in self._tracks.items()
            if (now - float(track["last_seen"])) > max_age_sec
        ]
        for track_id in stale_ids:
            self._tracks.pop(track_id, None)


_motion_tracker = _MotionTracker()


def _load_model():
    """Load YOLO model once and reuse it across all detections."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # expect best.pt to be in backend/ (same folder as this package's parent)
                model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "best.pt")
                _model = YOLO(model_path)
    return _model


def _extract_counts_from_result(result):
    """Build a class-name -> count mapping from a single YOLO result object."""
    counts = {}
    cls_vals = getattr(result.boxes, "cls", None)
    names = getattr(result, "names", None) or {}

    if cls_vals is not None:
        try:
            arr = np.array(cls_vals).astype(int).flatten()
            for idx in arr:
                if isinstance(names, dict):
                    name = names.get(int(idx), str(int(idx)))
                else:
                    try:
                        name = names[int(idx)]
                    except Exception:
                        name = str(int(idx))
                counts[name] = counts.get(name, 0) + 1
        except Exception:
            # fallback: best-effort extraction
            try:
                for box in getattr(result.boxes, "data", []):
                    idx = int(getattr(box, "cls", -1))
                    if idx >= 0:
                        if isinstance(names, dict):
                            name = names.get(idx, str(idx))
                        else:
                            name = names[idx] if idx < len(names) else str(idx)
                        counts[name] = counts.get(name, 0) + 1
            except Exception:
                pass

    return counts


def _get_zone(x_center, frame_width):
    left_limit = frame_width // 3
    right_limit = 2 * frame_width // 3
    if x_center < left_limit:
        return "left"
    if x_center < right_limit:
        return "center"
    return "right"


def _estimate_distance_m(label, bbox_width_px, focal_length_px=700.0, frame_width_px=1280):
    if bbox_width_px <= 0:
        return 99.0
    real_width = KNOWN_OBJECT_WIDTHS_M.get(label, 0.5)
    distance = (real_width * float(focal_length_px)) / float(bbox_width_px)
    approx_scale = max(frame_width_px / float(bbox_width_px), 1.0)
    fallback_distance = min(8.0, 0.35 * approx_scale)
    if distance <= 0 or distance > 12.0:
        return round(fallback_distance, 2)
    return round(distance, 2)


def _proximity(distance_m):
    if distance_m < 1.0:
        return "very_close"
    if distance_m <= 2.0:
        return "caution"
    return "safe"


def _build_instruction(language, objects):
    lang = language if language in TRANSLATIONS else "en"
    t = TRANSLATIONS[lang]

    if not objects:
        return t["path_clear"]

    closest = min(objects, key=lambda d: d["distance_m"])

    if closest["zone"] == "center" and closest["motion"] == "moving" and closest["distance_m"] <= 1.5:
        return t["moving_ahead_stop"].format(dist=f"{closest['distance_m']:.1f}")

    if closest["proximity"] == "very_close":
        return t["very_close"]

    if closest["zone"] == "left":
        if closest["proximity"] == "caution":
            return t["caution"].format(dist=f"{closest['distance_m']:.1f}") + " " + t["move_right"]
        return t["move_right"]

    if closest["zone"] == "right":
        if closest["proximity"] == "caution":
            return t["caution"].format(dist=f"{closest['distance_m']:.1f}") + " " + t["move_left"]
        return t["move_left"]

    if closest["zone"] == "center":
        if closest["proximity"] in {"very_close", "caution"}:
            return t["center_stop"]
        return t["caution"].format(dist=f"{closest['distance_m']:.1f}")

    return t["path_clear"]


def _draw_navigation_overlay(frame, objects, instruction):
    h, w = frame.shape[:2]
    left_line = w // 3
    right_line = 2 * w // 3
    cv2.line(frame, (left_line, 0), (left_line, h), (255, 255, 0), 2)
    cv2.line(frame, (right_line, 0), (right_line, h), (255, 255, 0), 2)

    for obj in objects:
        x1, y1, x2, y2 = obj["bbox"]
        if obj["proximity"] == "very_close":
            color = (0, 0, 255)
        elif obj["proximity"] == "caution":
            color = (0, 165, 255)
        else:
            color = (0, 255, 0)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        txt = f"{obj['label']} | {obj['distance_m']:.1f}m | {obj['motion']} | {obj['zone']}"
        cv2.putText(
            frame,
            txt,
            (x1, max(22, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    cv2.rectangle(frame, (10, h - 50), (w - 10, h - 10), (0, 0, 0), -1)
    cv2.putText(
        frame,
        instruction,
        (20, h - 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def _encode_frame_to_data_url(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    jpg_bytes = buf.tobytes()
    b64 = base64.b64encode(jpg_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def detect_image(image_path, conf=0.25, language="en", focal_length_px=700.0):
    """Run YOLO detection on a single image file.

    Returns (counts_dict, annotated_data_url_or_None, navigation_dict).
    """
    model = _load_model()

    frame = cv2.imread(image_path)
    if frame is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    results = model(frame, conf=conf)
    if len(results) == 0:
        navigation = {
            "instruction": _build_instruction(language, []),
            "objects": [],
            "zones": {"left": 0, "center": 0, "right": 0},
        }
        return {}, _encode_frame_to_data_url(frame), navigation

    r = results[0]

    # Build counts: class name -> count
    counts = _extract_counts_from_result(r)

    # Build per-object navigation data.
    objects = []
    names = getattr(r, "names", None) or {}
    boxes = getattr(r, "boxes", None)
    frame_h, frame_w = frame.shape[:2]

    if boxes is not None:
        for box in boxes:
            try:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                cls_idx = int(box.cls[0].item()) if box.cls is not None else -1
                conf_score = float(box.conf[0].item()) if box.conf is not None else 0.0

                if isinstance(names, dict):
                    label = names.get(cls_idx, str(cls_idx))
                else:
                    label = names[cls_idx] if cls_idx < len(names) else str(cls_idx)

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                zone = _get_zone(cx, frame_w)
                bbox_width = max(1, x2 - x1)
                distance_m = _estimate_distance_m(
                    label=label,
                    bbox_width_px=bbox_width,
                    focal_length_px=focal_length_px,
                    frame_width_px=frame_w,
                )
                prox = _proximity(distance_m)
                motion = _motion_tracker.classify_motion(label, (cx, cy))

                objects.append(
                    {
                        "label": label,
                        "confidence": round(conf_score, 3),
                        "bbox": [x1, y1, x2, y2],
                        "zone": zone,
                        "distance_m": distance_m,
                        "proximity": prox,
                        "motion": motion,
                    }
                )
            except Exception:
                continue

    _motion_tracker.prune()

    zone_counts = {
        "left": sum(1 for o in objects if o["zone"] == "left"),
        "center": sum(1 for o in objects if o["zone"] == "center"),
        "right": sum(1 for o in objects if o["zone"] == "right"),
    }
    instruction = _build_instruction(language, objects)

    annotated_data_url = None
    try:
        overlay = frame.copy()
        _draw_navigation_overlay(overlay, objects, instruction)
        annotated_data_url = _encode_frame_to_data_url(overlay)
    except Exception:
        annotated_data_url = None

    navigation = {
        "instruction": instruction,
        "objects": objects,
        "zones": zone_counts,
    }

    return counts, annotated_data_url, navigation


def detect_video(video_path, conf=0.25, frame_skip=5, max_frames=None):
    """Run YOLO detection on a video file.

    The video is sampled every ``frame_skip`` frames to control cost.

    Returns (total_counts, [best_annotated_frame_name], frames_processed).
    Only a single best annotated frame (with the most objects) is saved.
    """
    model = _load_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    total_counts = {}
    best_annotated_data_url = None
    best_objects = -1
    frames_processed = 0
    frame_index = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_skip > 1 and (frame_index % frame_skip) != 0:
                frame_index += 1
                continue

            frame_index += 1
            if max_frames is not None and frames_processed >= max_frames:
                break

            # Run detection on this frame
            results = model(frame, conf=conf)
            if not results or len(results) == 0:
                continue

            r = results[0]
            frame_counts = _extract_counts_from_result(r)
            for name, cnt in frame_counts.items():
                total_counts[name] = total_counts.get(name, 0) + cnt

            # Track the single best frame (with the most detected objects)
            frame_total = sum(frame_counts.values())
            if frame_total <= 0:
                frames_processed += 1
                continue

            if frame_total > best_objects:
                try:
                    annotated = r.plot()
                    try:
                        annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
                    except Exception:
                        annotated_bgr = annotated

                    ok, buf = cv2.imencode(".jpg", annotated_bgr)
                    if ok:
                        jpg_bytes = buf.tobytes()
                        b64 = base64.b64encode(jpg_bytes).decode("ascii")
                        best_annotated_data_url = f"data:image/jpeg;base64,{b64}"
                        best_objects = frame_total
                except Exception:
                    # If annotation fails, skip but keep counts
                    pass

            frames_processed += 1
    finally:
        cap.release()

    annotated_frames = [best_annotated_data_url] if best_annotated_data_url else []
    return total_counts, annotated_frames, frames_processed

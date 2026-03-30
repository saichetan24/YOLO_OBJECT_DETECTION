import argparse
import math
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
from ultralytics import YOLO


# Approximate real-world widths in meters for distance estimation.
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
        "status": "{motion} {label} in {zone} at {dist} meters",
        "moving": "Moving",
        "static": "Static",
        "zone_left": "left zone",
        "zone_center": "center zone",
        "zone_right": "right zone",
    },
    "hi": {
        "path_clear": "रास्ता साफ है, आगे बढ़ें",
        "move_left": "दाईं ओर बाधा है, बाईं ओर जाएं",
        "move_right": "बाईं ओर बाधा है, दाईं ओर जाएं",
        "center_stop": "सामने बाधा है, रुकें या बाईं या दाईं ओर जाएं",
        "moving_ahead_stop": "चलती हुई वस्तु सामने {dist} मीटर पर है। रुकें",
        "very_close": "बहुत नजदीक बाधा है। तुरंत रुकें",
        "caution": "सामने बाधा {dist} मीटर पर है। सावधानी से चलें",
        "status": "{zone} में {motion} {label}, दूरी {dist} मीटर",
        "moving": "चलती हुई",
        "static": "स्थिर",
        "zone_left": "बायां क्षेत्र",
        "zone_center": "मध्य क्षेत्र",
        "zone_right": "दायां क्षेत्र",
    },
    "te": {
        "path_clear": "మార్గం ఖాళీగా ఉంది, ముందుకు వెళ్లండి",
        "move_left": "కుడి వైపు అడ్డంకి ఉంది, ఎడమవైపు కదలండి",
        "move_right": "ఎడమ వైపు అడ్డంకి ఉంది, కుడివైపు కదలండి",
        "center_stop": "ముందు అడ్డంకి ఉంది, ఆగండి లేదా ఎడమ/కుడి వైపు కదలండి",
        "moving_ahead_stop": "కదులుతున్న వస్తువు ముందు {dist} మీటర్ల దూరంలో ఉంది. ఆగండి",
        "very_close": "చాలా దగ్గరలో అడ్డంకి ఉంది. వెంటనే ఆగండి",
        "caution": "ముందు అడ్డంకి {dist} మీటర్ల దూరంలో ఉంది. జాగ్రత్తగా కదలండి",
        "status": "{zone}లో {motion} {label}, దూరం {dist} మీటర్లు",
        "moving": "కదులుతున్న",
        "static": "స్థిర",
        "zone_left": "ఎడమ జోన్",
        "zone_center": "మధ్య జోన్",
        "zone_right": "కుడి జోన్",
    },
}


@dataclass
class DetectionObject:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    center: Tuple[int, int]
    zone: str
    distance_m: float
    proximity: str
    motion: str


class SpeechAssistant:
    def __init__(self, language: str = "en", cooldown_sec: float = 2.5):
        self.language = language if language in TRANSLATIONS else "en"
        self.cooldown_sec = cooldown_sec
        self.last_spoken = ""
        self.last_spoken_time = 0.0
        self._queue = queue.Queue()
        self._engine = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _init_engine(self) -> bool:
        if self._engine is not None:
            return True
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 165)
            self._engine.setProperty("volume", 1.0)
            return True
        except Exception:
            self._engine = None
            return False

    def _worker(self):
        while True:
            text = self._queue.get()
            try:
                if self._init_engine():
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def speak(self, text: str):
        if not text:
            return
        now = time.time()
        if text == self.last_spoken and (now - self.last_spoken_time) < self.cooldown_sec:
            return
        self.last_spoken = text
        self.last_spoken_time = now
        self._queue.put(text)


class MotionTracker:
    def __init__(self, move_threshold_px: float = 18.0, max_match_distance_px: float = 110.0):
        self.move_threshold_px = move_threshold_px
        self.max_match_distance_px = max_match_distance_px
        self._tracks: Dict[int, Dict[str, object]] = {}
        self._next_id = 1

    @staticmethod
    def _distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        return math.hypot(float(p1[0] - p2[0]), float(p1[1] - p2[1]))

    def classify_motion(self, label: str, center: Tuple[int, int]) -> str:
        best_id = None
        best_dist = float("inf")

        for track_id, track in self._tracks.items():
            if track["label"] != label:
                continue
            d = self._distance(center, track["center"])
            if d < best_dist and d <= self.max_match_distance_px:
                best_id = track_id
                best_dist = d

        if best_id is None:
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = {"label": label, "center": center, "last_seen": time.time()}
            return "static"

        prev_center = self._tracks[best_id]["center"]
        moved = self._distance(center, prev_center)
        self._tracks[best_id]["center"] = center
        self._tracks[best_id]["last_seen"] = time.time()
        return "moving" if moved >= self.move_threshold_px else "static"

    def prune(self, max_age_sec: float = 1.5):
        now = time.time()
        stale_ids = [
            track_id
            for track_id, track in self._tracks.items()
            if (now - float(track["last_seen"])) > max_age_sec
        ]
        for track_id in stale_ids:
            self._tracks.pop(track_id, None)


def get_zone(x_center: int, frame_width: int) -> str:
    left_limit = frame_width // 3
    right_limit = 2 * frame_width // 3
    if x_center < left_limit:
        return "left"
    if x_center < right_limit:
        return "center"
    return "right"


def estimate_distance_m(
    label: str,
    bbox_width_px: int,
    focal_length_px: float = 700.0,
    frame_width_px: int = 1280,
) -> float:
    if bbox_width_px <= 0:
        return 99.0

    real_width = KNOWN_OBJECT_WIDTHS_M.get(label, 0.5)
    distance = (real_width * focal_length_px) / float(bbox_width_px)

    # Fallback stabilization when box width is tiny/noisy.
    approx_scale = max(frame_width_px / float(bbox_width_px), 1.0)
    fallback_distance = min(8.0, 0.35 * approx_scale)
    if distance <= 0 or distance > 12.0:
        return round(fallback_distance, 2)

    return round(distance, 2)


def get_proximity(distance_m: float) -> str:
    if distance_m < 1.0:
        return "very_close"
    if distance_m <= 2.0:
        return "caution"
    return "safe"


def detect_objects(
    model: YOLO,
    frame,
    motion_tracker: MotionTracker,
    conf_threshold: float,
    focal_length_px: float,
) -> List[DetectionObject]:
    h, w = frame.shape[:2]
    results = model.predict(frame, conf=conf_threshold, verbose=False)
    if not results:
        return []

    result = results[0]
    detections: List[DetectionObject] = []

    if result.boxes is None:
        return detections

    names = result.names if isinstance(result.names, dict) else {}

    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

        cls_id = int(box.cls[0].item()) if box.cls is not None else -1
        conf = float(box.conf[0].item()) if box.conf is not None else 0.0
        label = names.get(cls_id, str(cls_id))

        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        zone = get_zone(cx, w)

        bbox_w = max(1, x2 - x1)
        distance_m = estimate_distance_m(
            label=label,
            bbox_width_px=bbox_w,
            focal_length_px=focal_length_px,
            frame_width_px=w,
        )
        proximity = get_proximity(distance_m)
        motion = motion_tracker.classify_motion(label, (cx, cy))

        detections.append(
            DetectionObject(
                label=label,
                confidence=conf,
                bbox=(x1, y1, x2, y2),
                center=(cx, cy),
                zone=zone,
                distance_m=distance_m,
                proximity=proximity,
                motion=motion,
            )
        )

    motion_tracker.prune()
    return detections


def _zone_translation(language: str, zone: str) -> str:
    t = TRANSLATIONS[language]
    if zone == "left":
        return t["zone_left"]
    if zone == "right":
        return t["zone_right"]
    return t["zone_center"]


def build_navigation_instruction(language: str, detections: List[DetectionObject]) -> str:
    t = TRANSLATIONS[language]
    if not detections:
        return t["path_clear"]

    # Prioritize closest obstacle.
    closest = min(detections, key=lambda d: d.distance_m)

    if closest.zone == "center" and closest.motion == "moving" and closest.distance_m <= 1.5:
        return t["moving_ahead_stop"].format(dist=f"{closest.distance_m:.1f}")

    if closest.proximity == "very_close":
        return t["very_close"]

    if closest.zone == "left":
        if closest.proximity == "caution":
            return t["caution"].format(dist=f"{closest.distance_m:.1f}") + " " + t["move_right"]
        return t["move_right"]

    if closest.zone == "right":
        if closest.proximity == "caution":
            return t["caution"].format(dist=f"{closest.distance_m:.1f}") + " " + t["move_left"]
        return t["move_left"]

    if closest.zone == "center":
        if closest.proximity in {"very_close", "caution"}:
            return t["center_stop"]
        return t["caution"].format(dist=f"{closest.distance_m:.1f}")

    return t["path_clear"]


def draw_visual_feedback(frame, language: str, detections: List[DetectionObject], instruction: str):
    h, w = frame.shape[:2]

    # Zone lines.
    left_line = w // 3
    right_line = 2 * w // 3
    cv2.line(frame, (left_line, 0), (left_line, h), (255, 255, 0), 2)
    cv2.line(frame, (right_line, 0), (right_line, h), (255, 255, 0), 2)

    for d in detections:
        x1, y1, x2, y2 = d.bbox
        color = (0, 0, 255) if d.proximity == "very_close" else (0, 165, 255) if d.proximity == "caution" else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label_text = (
            f"{d.label} | {d.distance_m:.1f}m | "
            f"{'Moving' if d.motion == 'moving' else 'Static'} | {d.zone}"
        )
        cv2.putText(
            frame,
            label_text,
            (x1, max(20, y1 - 8)),
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

    lang_text = f"Language: {language.upper()}"
    cv2.putText(frame, lang_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)


def parse_args():
    parser = argparse.ArgumentParser(description="Real-time blind navigation assistant")
    default_model = os.path.join(os.path.dirname(__file__), "best.pt")
    parser.add_argument("--model", type=str, default=default_model, help="YOLO model path")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=["en", "hi", "te"],
        help="Voice and instruction language",
    )
    parser.add_argument(
        "--focal-length",
        type=float,
        default=700.0,
        help="Approximate focal length in pixels for distance estimation",
    )
    parser.add_argument(
        "--frame-skip",
        type=int,
        default=1,
        help="Process every Nth frame for speed",
    )
    return parser.parse_args()


def run_navigation_assistant():
    args = parse_args()

    model = YOLO(args.model)
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        raise RuntimeError("Unable to open webcam")

    speech = SpeechAssistant(language=args.language, cooldown_sec=2.5)
    motion_tracker = MotionTracker()

    frame_index = 0
    last_detections: List[DetectionObject] = []
    last_instruction = TRANSLATIONS[args.language]["path_clear"]

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_index += 1

        if args.frame_skip <= 1 or frame_index % args.frame_skip == 0:
            last_detections = detect_objects(
                model=model,
                frame=frame,
                motion_tracker=motion_tracker,
                conf_threshold=args.conf,
                focal_length_px=args.focal_length,
            )
            last_instruction = build_navigation_instruction(args.language, last_detections)
            speech.speak(last_instruction)

        draw_visual_feedback(frame, args.language, last_detections, last_instruction)

        cv2.imshow("Blind Navigation Assistant", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("1"):
            speech.language = "en"
            args.language = "en"
        if key == ord("2"):
            speech.language = "hi"
            args.language = "hi"
        if key == ord("3"):
            speech.language = "te"
            args.language = "te"

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_navigation_assistant()

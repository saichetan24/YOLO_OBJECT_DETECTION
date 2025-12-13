import os
import threading
from ultralytics import YOLO
import numpy as np

# Load model once at import time (lazy load)
_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # expect best.pt to be in backend/ (same folder as this package's parent)
                model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "best.pt")
                _model = YOLO(model_path)
    return _model


def detect_image(image_path, conf=0.25):
    """Run YOLO detection on the given image path and return list of detected class names.

    Args:
        image_path (str): path to image file
        conf (float): confidence threshold

    Returns:
        list[str]: unique detected class names (strings)
    """
    model = _load_model()

    # ultralytics model expects either file path or numpy array
    results = model(image_path, conf=conf)
    if len(results) == 0:
        return []

    r = results[0]

    # Build counts: class name -> count
    counts = {}
    cls_vals = getattr(r.boxes, "cls", None)
    names = getattr(r, "names", None) or {}
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
                for box in getattr(r.boxes, "data", []):
                    idx = int(getattr(box, "cls", -1))
                    if idx >= 0:
                        if isinstance(names, dict):
                            name = names.get(idx, str(idx))
                        else:
                            name = names[idx] if idx < len(names) else str(idx)
                        counts[name] = counts.get(name, 0) + 1
            except Exception:
                pass

    # Save annotated image returned by ultralytics
    try:
        annotated = r.plot()  # numpy array (H,W,3) in RGB or BGR depending on version
        # convert to BGR if needed for cv2.imwrite expecting BGR; ultralytics usually returns RGB
        try:
            import cv2
            # assume annotated in RGB, convert to BGR
            annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
        except Exception:
            annotated_bgr = annotated

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        base = os.path.basename(image_path)
        annotated_name = f"annotated-{base}"
        annotated_path = os.path.join(upload_dir, annotated_name)
        try:
            import cv2
            cv2.imwrite(annotated_path, annotated_bgr)
        except Exception:
            # try with imageio as fallback
            try:
                import imageio
                imageio.imsave(annotated_path, annotated)
            except Exception:
                annotated_path = None
    except Exception:
        annotated_path = None

    # Return counts dict and annotated filename (relative path)
    return counts, (os.path.basename(annotated_path) if annotated_path else None)

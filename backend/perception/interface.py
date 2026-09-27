"""
Track A owns this file.

REAL implementation (v1):
- Detection: YOLOv8, pre-trained on COCO (no custom training needed yet --
  COCO already includes furniture-relevant classes: chair, couch, bed,
  dining table, tv, potted plant). Fine-tuning on HomeObjects-3K/your own
  room dataset is future work -- this already gives real, non-fake results.
- Colour: real K-means on the uploaded image.
- Empty space: simple heuristic (1 - fraction of image covered by detected
  boxes). Real segmentation is future work -- documented honestly below.
- Style: NOT yet implemented for real. Rather than fake a label, this
  returns confidence 0 and needs_confirmation=True, which is exactly the
  "flag low-confidence predictions for user confirmation instead of
  auto-committing" behaviour your synopsis's Safety section describes.
  Swap in a trained MobileNetV3 classifier here later -- nothing else in
  the codebase needs to change, the contract stays identical.
"""

import cv2
import numpy as np
from sklearn.cluster import KMeans
from ultralytics import YOLO

STYLE_CONFIDENCE_THRESHOLD = 0.6

# COCO classes relevant to furniture/interior. Full list:
# https://docs.ultralytics.com/datasets/detect/coco/
FURNITURE_CLASSES = {"chair", "couch", "bed", "dining table", "tv", "potted plant"}

_model = None  # loaded lazily so importing this file doesn't trigger a download


def _get_model():
    global _model
    if _model is None:
        _model = YOLO("yolov8n.pt")  # auto-downloads on first run (~6MB)
    return _model


def _extract_colors(image_rgb: np.ndarray, n_colors: int = 5) -> list:
    pixels = image_rgb.reshape(-1, 3)
    if len(pixels) > 20000:  # sample for speed on large images
        idx = np.random.choice(len(pixels), 20000, replace=False)
        pixels = pixels[idx]
    kmeans = KMeans(n_clusters=n_colors, n_init=10, random_state=42).fit(pixels)
    return ["#%02x%02x%02x" % tuple(c) for c in kmeans.cluster_centers_.astype(int)]


def analyze_room(image_path: str) -> dict:
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise ValueError(f"Could not read image at {image_path}")
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w = image_bgr.shape[:2]

    results = _get_model()(image_bgr, verbose=False)[0]
    detections = []
    covered_area = 0
    for box in results.boxes:
        label = results.names[int(box.cls[0])]
        if label not in FURNITURE_CLASSES:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = float(box.conf[0])
        detections.append({
            "label": label,
            "bbox": [round(x1), round(y1), round(x2), round(y2)],
            "confidence": round(confidence, 2),
        })
        covered_area += (x2 - x1) * (y2 - y1)

    empty_ratio = max(0.0, 1 - (covered_area / (w * h)))
    empty_space = [{"region": "floor", "bbox": [0, round(h * 0.7), w, h], "area_ratio": round(empty_ratio, 2)}]

    dominant_colors = _extract_colors(image_rgb)

    # Style classifier not trained yet -- honest placeholder, see docstring.
    style_confidence = 0.0
    return {
        "detections": detections,
        "empty_space": empty_space,
        "dominant_colors": dominant_colors,
        "style": {"label": "unclassified", "confidence": style_confidence},
        "needs_confirmation": style_confidence < STYLE_CONFIDENCE_THRESHOLD,
    }

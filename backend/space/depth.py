"""
Estimates the room size (width x length in metres) from ONE photo, so the
user does not have to type it.

How it works
1. Depth Anything V2 (Metric-Indoor, a pretrained model from HuggingFace)
   predicts, for every pixel, how many metres away that point is.
2. With a typical phone-camera field of view we turn each pixel + its depth
   into a real-world position (X sideways, Z forward).
3. Room length = distance to the far wall (Z). Room width = how far apart the
   left and right edges are at that distance (X).

Honest limits (say them in the review): one photo only shows part of a room,
so this is an ESTIMATE, usually within about 20-30 percent. The page shows it
and lets the user correct it. The camera's exact field of view is unknown, so
a typical 68 degrees along the photo's long side is assumed.

The model (about 100 MB) downloads automatically the first time it is used.
If anything fails (no internet, package missing) this returns None and the
app simply skips the floor-space check.
"""

import math
from typing import Optional

import numpy as np

MODEL_ID = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"
LONG_SIDE_FOV_DEG = 68.0     # typical phone main camera, across the longer image side
MIN_M, MAX_M = 1.5, 10.0     # sanity limits for a room side

_model = None
_processor = None


def _load():
    global _model, _processor
    if _model is None:
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        _processor = AutoImageProcessor.from_pretrained(MODEL_ID)
        _model = AutoModelForDepthEstimation.from_pretrained(MODEL_ID).eval()
    return _model, _processor


def predict_depth(image_rgb: np.ndarray) -> np.ndarray:
    """Returns an H x W array of distances in metres."""
    import torch
    from PIL import Image
    model, processor = _load()
    h, w = image_rgb.shape[:2]
    inputs = processor(images=Image.fromarray(image_rgb), return_tensors="pt")
    with torch.no_grad():
        pred = model(**inputs).predicted_depth            # (1, h', w') in metres
    pred = torch.nn.functional.interpolate(pred.unsqueeze(1), size=(h, w),
                                           mode="bicubic", align_corners=False)
    return pred.squeeze().cpu().numpy()


def room_size_from_depth(depth: np.ndarray, fov_deg: float = LONG_SIDE_FOV_DEG) -> Optional[dict]:
    """Pure geometry (no model): depth map in metres -> room width/length."""
    h, w = depth.shape
    f = max(h, w) / (2 * math.tan(math.radians(fov_deg / 2)))   # focal length in pixels
    # Middle band of the image: walls, not the floor right under the camera or the ceiling.
    band = depth[int(h * 0.3):int(h * 0.7), :]
    band = band[:, ::4]
    if band.size == 0 or not np.isfinite(band).all():
        return None
    us = (np.arange(0, w, 4)[: band.shape[1]] - w / 2.0)
    x = band * us[None, :] / f                                  # sideways position in metres
    length = float(np.percentile(band, 90))                     # far wall distance
    width = float(np.percentile(x, 97) - np.percentile(x, 3))   # visible width
    if length <= 0 or width <= 0:
        return None
    length = min(max(length, MIN_M), MAX_M)
    width = min(max(width, MIN_M), MAX_M)
    return {"width_m": round(width, 1), "length_m": round(length, 1)}


def estimate_room_size(image_path: str) -> Optional[dict]:
    """Photo file -> {"width_m", "length_m", "source"} or None if it can't be done."""
    try:
        import cv2
        bgr = cv2.imread(image_path)
        if bgr is None:
            return None
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        result = room_size_from_depth(predict_depth(rgb))
        if result:
            result["source"] = "depth-anything-v2-metric-indoor"
        return result
    except Exception as e:  # never break the whole request because of this
        print(f"[space.depth] room size estimate skipped: {e}")
        return None

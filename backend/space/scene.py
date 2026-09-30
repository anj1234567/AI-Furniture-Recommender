"""
One depth prediction per photo -> everything the app needs about the space:
room size, floor plane / camera height (for the 3D-in-photo view), ceiling height.
"""

import math
import os
import numpy as np

from .depth import predict_depth, room_size_from_depth, LONG_SIDE_FOV_DEG
from .floor import fit_floor, ceiling_height, DEFAULT_CAM_HEIGHT
from .mesh import depth_grid

_cache = {}


def _camera(w, h, up_cv, cam_h, source, ratio=None, ceiling=None):
    f = max(h, w) / (2 * math.tan(math.radians(LONG_SIDE_FOV_DEG / 2)))
    up = np.asarray(up_cv, dtype=float)
    return {
        "aspect": round(w / h, 4),
        "fov_v_deg": round(math.degrees(2 * math.atan((h / 2) / f)), 2),
        # same vector in three.js camera coords (x right, y UP, z backward): flip y and z
        "up": [round(float(up[0]), 4), round(float(-up[1]), 4), round(float(-up[2]), 4)],
        "cam_height_m": cam_h,
        "floor_source": source,          # "depth" or "assumed"
        "inlier_ratio": ratio,
        "ceiling_height_m": ceiling,
    }


def analyze_scene(image_path: str) -> dict:
    """Never raises. Returns {"room": {...}|None, "camera": {...}, "mesh": {...}|None}."""
    import cv2
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise ValueError(f"Could not read image at {image_path}")
    h, w = bgr.shape[:2]
    key = (image_path, os.path.getmtime(image_path), w, h)
    if key in _cache:
        return _cache[key]

    fallback = {"room": None, "mesh": None, "camera": _camera(w, h, [0, -1, 0], DEFAULT_CAM_HEIGHT, "assumed")}
    try:
        depth = predict_depth(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        room = room_size_from_depth(depth)
        fl = fit_floor(depth, LONG_SIDE_FOV_DEG)
        if fl:
            ceil = ceiling_height(depth, LONG_SIDE_FOV_DEG, fl["up"], fl["cam_height_m"])
            if ceil is None or not (2.3 <= ceil <= 3.6):   # depth from one photo is unreliable up there
                ceil = 2.7
            cam = _camera(w, h, fl["up"], fl["cam_height_m"], "depth", fl["inlier_ratio"], ceil)
        else:
            cam = fallback["camera"]
        result = {"room": room, "camera": cam, "mesh": depth_grid(depth)}
    except Exception as e:                      # depth model missing / offline / etc.
        print(f"[space.scene] depth analysis skipped: {e}")
        result = fallback
    if len(_cache) > 20:
        _cache.clear()
    _cache[key] = result
    return result

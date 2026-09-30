"""
Turns the metric depth map into a small grid the browser can build a textured
3D mesh of the real room from ("Room in 3D" view).

The grid is sent as base64 of little-endian uint16 centimetres (about 45 KB for a
176 x 132 grid). The camera field of view is already sent in `scene.camera`, so
the page can turn (column, row, depth) into a 3D point on its own.
"""

import base64

import cv2
import numpy as np

MAX_SIDE = 176


def depth_grid(depth: np.ndarray, max_side: int = MAX_SIDE) -> dict:
    h, w = depth.shape
    s = max_side / max(h, w)
    gw, gh = max(2, int(round(w * s))), max(2, int(round(h * s)))
    small = cv2.resize(depth.astype(np.float32), (gw, gh), interpolation=cv2.INTER_AREA)
    small = np.nan_to_num(small, nan=float(np.nanmedian(small)) if np.isfinite(small).any() else 3.0)
    small = cv2.bilateralFilter(small, 5, 0.15, 3)       # smooth noise but keep object edges
    cm = np.clip(small * 100.0, 1, 65535).astype("<u2")
    return {
        "w": gw,
        "h": gh,
        "depth_cm_b64": base64.b64encode(cm.tobytes()).decode("ascii"),
        "near_m": round(float(np.percentile(small, 2)), 2),
        "median_m": round(float(np.median(small)), 2),
        "far_m": round(float(np.percentile(small, 98)), 2),
    }


def decode_grid(g: dict) -> np.ndarray:
    """Inverse of depth_grid (used by tests)."""
    raw = np.frombuffer(base64.b64decode(g["depth_cm_b64"]), dtype="<u2")
    return raw.reshape(g["h"], g["w"]).astype(np.float32) / 100.0

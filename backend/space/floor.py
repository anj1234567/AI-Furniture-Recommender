"""
Finds the FLOOR PLANE and the CEILING HEIGHT from a metric depth map.

Why: to draw a 3D sofa onto the user's photo so that it sits on the floor with the
right perspective, we need to know where the floor is relative to the camera.

Method (all plain geometry, no extra model):
 1. Turn every pixel + its depth into a 3D point in the camera's frame
    (x right, y DOWN, z forward -- the OpenCV convention).
 2. Take pixels from the lower part of the photo (mostly floor) and fit a plane
    with RANSAC, which ignores the furniture and walls mixed in.
 3. The plane gives the camera height above the floor and the "up" direction, i.e.
    how much the phone was tilted.
 4. Pixels in the top part of the photo give the ceiling height when it is visible.
"""

import math
import numpy as np

DEFAULT_CAM_HEIGHT = 1.4      # metres, phone held at chest height (used only if the fit fails)


def _backproject(depth, fov_deg, rows=None, step=6):
    h, w = depth.shape
    f = max(h, w) / (2 * math.tan(math.radians(fov_deg / 2)))
    r0, r1 = rows if rows else (0, h)
    vs, us = np.mgrid[r0:r1:step, 0:w:step]
    z = depth[r0:r1:step, 0:w:step].astype(np.float64)
    x = (us - w / 2.0) * z / f
    y = (vs - h / 2.0) * z / f
    pts = np.stack([x, y, z], -1).reshape(-1, 3)
    return pts[np.isfinite(pts).all(1) & (pts[:, 2] > 0.2)], f


def fit_floor(depth: np.ndarray, fov_deg: float, seed: int = 0):
    """Returns dict with `up` (unit vector, OpenCV camera coords), `cam_height_m`,
    `inlier_ratio`, or None when no believable floor is found."""
    h, w = depth.shape
    pts, _ = _backproject(depth, fov_deg, rows=(int(h * 0.55), h))
    if len(pts) < 200:
        return None
    rng = np.random.default_rng(seed)
    thr = max(0.03, 0.02 * float(np.median(pts[:, 2])))
    best, best_n = None, 0
    for _ in range(300):
        a, b, c = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n /= norm
        cnt = int((np.abs((pts - a) @ n) < thr).sum())
        if cnt > best_n:
            best, best_n = (n, a), cnt
    if best is None:
        return None
    n, a = best
    inl = np.abs((pts - a) @ n) < thr
    # refine on the inliers (least squares plane)
    P = pts[inl]
    centre = P.mean(0)
    n = np.linalg.svd(P - centre)[2][-1]
    if n @ centre > 0:          # make `up` point from the floor towards the camera
        n = -n
    height = float(-(n @ centre))
    tilt = math.degrees(math.acos(min(1.0, abs(n[1]))))     # angle away from "straight up in the photo"
    ratio = float(inl.mean())
    if ratio < 0.25 or height < 0.3 or height > 3.0 or tilt > 60:
        return None
    return {"up": n.tolist(), "cam_height_m": round(height, 2), "inlier_ratio": round(ratio, 2)}


def ceiling_height(depth: np.ndarray, fov_deg: float, up, cam_height: float):
    """Height of the ceiling above the floor, if the top of the photo shows it."""
    h, _ = depth.shape
    pts, _ = _backproject(depth, fov_deg, rows=(0, int(h * 0.3)))
    if len(pts) < 100:
        return None
    above = pts @ np.asarray(up) + cam_height        # height of each point above the floor
    above = above[(above > 1.8) & (above < 5.0)]
    if len(above) < 100:
        return None
    return round(float(np.percentile(above, 90)), 1)

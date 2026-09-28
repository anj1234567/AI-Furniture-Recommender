"""
Layer 1: Image ingestion & preprocessing (from the project synopsis).

- assess_quality(): brightness / sharpness checks -> warnings for the user
- enhance_if_dark(): brightens dim photos (adaptive gamma + CLAHE) so the
  detector and colour extraction see the room more clearly.

Image size is never changed, so bounding boxes stay valid for the original photo.
"""

import math
import cv2
import numpy as np

DARK_THRESHOLD = 90      # mean grayscale (0-255) below this = "dark photo"
TARGET_BRIGHTNESS = 115  # brightness the enhancement aims for
BLUR_THRESHOLD = 60      # variance of Laplacian below this = "blurry photo"
MIN_SIDE = 400           # photos smaller than this (pixels) are low resolution
WARN_FLAT_RATIO = 0.5    # top-3 colours cover more than this = probably a screenshot/graphic
REJECT_FLAT_RATIO = 0.7  # above this the upload is rejected (real room photos are ~0.1-0.2)


def assess_quality(image_bgr: np.ndarray) -> dict:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Screenshots, documents and graphics are made of a few flat colours;
    # real photos spread over many. Measure how much the 3 commonest colours cover.
    small = cv2.resize(image_bgr, (256, max(1, int(256 * h / w))))
    q = (small // 8).reshape(-1, 3).astype(int)
    codes = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
    _, counts = np.unique(codes, return_counts=True)
    flat_ratio = float(np.sort(counts)[::-1][:3].sum() / counts.sum())

    warnings = []
    if flat_ratio > WARN_FLAT_RATIO:
        warnings.append("This looks like a screenshot or graphic, not a room photo. Results may be meaningless.")
    if brightness < DARK_THRESHOLD:
        warnings.append("Photo is dark. We brightened it for analysis; better lighting gives better results.")
    if sharpness < BLUR_THRESHOLD:
        warnings.append("Photo looks blurry. Try a sharper photo for more accurate detection.")
    if min(h, w) < MIN_SIDE:
        warnings.append("Photo resolution is low. A larger photo will improve detection.")

    return {
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 1),
        "is_dark": brightness < DARK_THRESHOLD,
        "flat_ratio": round(flat_ratio, 2),
        "warnings": warnings,
    }


def enhance_if_dark(image_bgr: np.ndarray, quality: dict) -> np.ndarray:
    """Return a brightened copy for dark photos, or the original unchanged."""
    if not quality["is_dark"]:
        return image_bgr

    mean = max(quality["brightness"], 1.0)
    # Adaptive gamma: darker photo -> stronger brightening (never darkens)
    gamma = math.log(TARGET_BRIGHTNESS / 255) / math.log(mean / 255)
    gamma = min(max(gamma, 0.5), 1.0)
    table = np.array([255 * (i / 255) ** gamma for i in range(256)]).astype("uint8")
    brightened = cv2.LUT(image_bgr, table)

    # CLAHE on the lightness channel: recovers local contrast in shadows
    lab = cv2.cvtColor(brightened, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

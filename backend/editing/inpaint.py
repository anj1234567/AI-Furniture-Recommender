"""
Removes objects from a room photo ("clear the room") so the user can see the
space empty and get recommendations for it.

Two engines, tried in this order:
1. LaMa (big-lama, TorchScript). A pretrained AI inpainting model: it invents
   believable floor / wall texture behind the removed object. Needs a one-time
   ~200 MB download into backend/editing/weights/ and PyTorch (already installed
   with ultralytics). Runs on a small crop around each object, so it takes a few seconds.
2. OpenCV Telea inpainting. Always available, but only smears nearby colours,
   so it looks blurry on big objects. Used when LaMa cannot be loaded.

Set the environment variable FURNITURE_NO_LAMA=1 to force the OpenCV engine.

The mask can come from detected boxes (refined with GrabCut so we erase the
object and not the whole rectangle) and/or from a mask the user painted.
"""

import os
import urllib.request

import cv2
import numpy as np

LAMA_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
WEIGHTS = os.path.join(os.path.dirname(__file__), "weights", "big-lama.pt")
LAMA_MAX_SIDE = 768         # LaMa runs on a crop around each removed object, never on the whole photo
CV_MAX_SIDE = 800

_lama = None
_lama_failed = False


# ---------------------------------------------------------------- masks

def _grabcut_box(bgr, box, margin_px):
    """Silhouette of the object inside `box`, or None when GrabCut is not convincing."""
    h, w = bgr.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    if bw < 16 or bh < 16:
        return None
    # work on a crop with some context around the box, at most ~400 px, for speed
    cx1, cy1 = max(0, x1 - margin_px), max(0, y1 - margin_px)
    cx2, cy2 = min(w, x2 + margin_px), min(h, y2 + margin_px)
    crop = bgr[cy1:cy2, cx1:cx2]
    s = min(1.0, 400.0 / max(crop.shape[:2]))
    small = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else crop.copy()
    rect = (int((x1 - cx1) * s), int((y1 - cy1) * s), max(2, int(bw * s)), max(2, int(bh * s)))
    gc = np.zeros(small.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(small, gc, rect, bgd, fgd, 4, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return None
    fg = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    frac = fg.sum() / max(1, rect[2] * rect[3])
    if frac < 0.30 or frac > 0.97:           # silhouette too small (missed) or ~ the whole box (no info)
        return None
    if s < 1:
        fg = cv2.resize(fg, (cx2 - cx1, cy2 - cy1), interpolation=cv2.INTER_NEAREST)
    full = np.zeros((h, w), np.uint8)
    full[cy1:cy2, cx1:cx2] = fg
    return full


def boxes_to_mask(shape, boxes, bgr=None, refine=True, pad=0.02):
    """boxes: [[x1,y1,x2,y2], ...] in pixels. Returns a uint8 mask (255 = remove)."""
    h, w = shape[:2]
    mask = np.zeros((h, w), np.uint8)
    for b in boxes:
        x1, y1, x2, y2 = [int(round(v)) for v in b]
        x1, x2 = sorted((max(0, min(w, x1)), max(0, min(w, x2))))
        y1, y2 = sorted((max(0, min(h, y1)), max(0, min(h, y2))))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        sil = _grabcut_box(bgr, (x1, y1, x2, y2), int(0.04 * max(h, w))) if (refine and bgr is not None) else None
        if sil is not None:
            # keep only the part of the silhouette inside the box, then add a small safety border
            box_only = np.zeros_like(sil)
            box_only[y1:y2, x1:x2] = sil[y1:y2, x1:x2]
            mask |= (box_only * 255).astype(np.uint8)
        else:
            mask[y1:y2, x1:x2] = 255
    return grow_mask(mask, pad)


def grow_mask(mask, frac):
    """Dilate a little: inpainting looks better if the edges/shadows of the object are inside the mask."""
    m = (mask > 127).astype(np.uint8) * 255
    k = max(3, int(round(frac * max(m.shape))) | 1)
    return cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))


# ---------------------------------------------------------------- engines

def _load_lama():
    global _lama, _lama_failed
    if _lama is not None or _lama_failed:
        return _lama
    if os.environ.get("FURNITURE_NO_LAMA") == "1":
        _lama_failed = True
        return None
    try:
        import torch
        os.makedirs(os.path.dirname(WEIGHTS), exist_ok=True)
        if not os.path.exists(WEIGHTS):
            print("[editing] downloading the LaMa inpainting model (~200 MB, one time only)...")
            tmp = WEIGHTS + ".part"
            urllib.request.urlretrieve(LAMA_URL, tmp)
            os.replace(tmp, WEIGHTS)
        _lama = torch.jit.load(WEIGHTS, map_location="cpu").eval()
        print("[editing] LaMa inpainting model loaded")
    except Exception as e:
        print(f"[editing] LaMa unavailable, using the OpenCV fallback: {e}")
        _lama_failed = True
    return _lama


def _run_lama(model, rgb, mask):
    """rgb: HxWx3 uint8, mask: HxW uint8 (255 = fill). Returns HxWx3 uint8."""
    import torch
    h, w = rgb.shape[:2]
    ph, pw = (-h) % 8, (-w) % 8
    img = np.pad(rgb, ((0, ph), (0, pw), (0, 0)), mode="symmetric")
    m = np.pad(mask, ((0, ph), (0, pw)), mode="symmetric")
    it = torch.from_numpy(img.astype(np.float32) / 255.0).permute(2, 0, 1)[None]
    mt = torch.from_numpy((m > 127).astype(np.float32))[None, None]
    with torch.inference_mode():
        out = model(it, mt)
    out = out[0].permute(1, 2, 0).cpu().numpy()
    out = out * (255.0 if out.max() <= 1.5 else 1.0)
    return np.clip(out, 0, 255).astype(np.uint8)[:h, :w]


def _lama_fill(bgr, mask):
    """Fill `mask` in `bgr` (usually a crop). Returns a BGR image the same size, or None if LaMa is unusable."""
    model = _load_lama()
    if model is None:
        return None
    try:
        h, w = bgr.shape[:2]
        s = min(1.0, LAMA_MAX_SIDE / max(h, w))      # crops are already small, so this is rarely below 1
        small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else bgr
        msmall = cv2.resize(mask, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST) if s < 1 else mask
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        out = _run_lama(model, rgb, msmall)
        outside = msmall < 128
        if outside.any() and float(np.abs(out.astype(np.int16) - rgb.astype(np.int16))[outside].mean()) > 12.0:
            print("[editing] LaMa output failed the sanity check, using the OpenCV fallback")
            return None
        out = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        return cv2.resize(out, (w, h), interpolation=cv2.INTER_LANCZOS4) if s < 1 else out
    except Exception as e:
        print(f"[editing] LaMa failed ({e}), using the OpenCV fallback")
        return None


def _opencv_fill(bgr, mask):
    radius = max(3, int(0.012 * max(bgr.shape[:2])))
    return cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)


def _add_grain(filled, crop, mask):
    """Inpainted areas are smoother than a real photo, which reads as 'blurry'.
    Add noise with the same strength as the untouched pixels around the object."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    detail = gray - cv2.GaussianBlur(gray, (0, 0), 1.5)
    outside = mask < 128
    if outside.sum() < 200:
        return filled
    sigma = float(detail[outside].std())
    sigma = min(max(sigma, 0.0), 6.0)
    if sigma < 0.5:
        return filled
    rng = np.random.default_rng(0)
    noise = rng.normal(0, sigma * 0.8, filled.shape[:2]).astype(np.float32)[..., None]
    return np.clip(filled.astype(np.float32) + noise * (mask[..., None] > 127), 0, 255).astype(np.uint8)


def _groups(mask):
    """Split the mask into separate objects so far-apart removals are processed as small crops."""
    k = max(3, int(0.06 * max(mask.shape)) | 1)
    near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, labels = cv2.connectedComponents((near > 0).astype(np.uint8))
    for i in range(1, n):
        part = np.where(labels == i, mask, 0).astype(np.uint8)
        if part.any():
            yield part


def remove_objects(bgr, mask):
    """Returns (cleaned BGR image, engine name: "lama" | "opencv").
    Each object is filled on a crop around it (fast, and the fill keeps the photo's own resolution);
    the rest of the photo stays pixel-identical."""
    mask = (mask > 127).astype(np.uint8) * 255
    if mask.shape[:2] != bgr.shape[:2]:
        mask = cv2.resize(mask, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
    if not mask.any():
        return bgr.copy(), "none"
    H, W = bgr.shape[:2]
    out = bgr.copy()
    engine = "lama"
    for part in _groups(mask):
        ys, xs = np.where(part > 0)
        x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        pad = int(max(96, 0.6 * max(x2 - x1, y2 - y1)))       # context for LaMa to copy texture from
        cx1, cy1, cx2, cy2 = max(0, x1 - pad), max(0, y1 - pad), min(W, x2 + pad), min(H, y2 + pad)
        crop, m = out[cy1:cy2, cx1:cx2], part[cy1:cy2, cx1:cx2]
        filled = _lama_fill(crop, m)
        if filled is None:
            filled, engine = _opencv_fill(crop, m), "opencv"
        filled = _add_grain(filled, crop, m)
        k = max(3, int(0.004 * max(H, W)) | 1)
        alpha = cv2.GaussianBlur(m.astype(np.float32) / 255.0, (k, k), 0)[..., None]
        alpha = np.maximum(alpha, (m > 127)[..., None].astype(np.float32))
        blended = crop.astype(np.float32) * (1 - alpha) + filled.astype(np.float32) * alpha
        out[cy1:cy2, cx1:cx2] = np.clip(blended, 0, 255).astype(np.uint8)
    return out, engine

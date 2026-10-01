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
LAMA_MAX_SIDE = 1024        # LaMa runs on a crop around each removed object, never on the whole photo
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


def boxes_to_mask(shape, boxes, bgr=None, refine=True, pad=0.035):
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


def _borrow_detail(detail, hole, src_ok):
    """Fine texture (grout lines, paint grain, noise) for the pixels in `hole`, copied from
    nearby places of the same photo where `src_ok` is True. Offsets grow outwards, so each
    hole pixel takes texture from the closest usable spot. Returns an array like `detail`."""
    h, w = hole.shape
    ys, xs = np.where(hole)
    y1, y2, x1, x2 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    out = np.zeros((h, w), np.float32)
    todo = hole[y1:y2, x1:x2].copy()
    rng = np.random.default_rng(1)
    r, rmax = 8.0, 1.6 * max(h, w)
    while r < rmax and todo.any():
        base = rng.uniform(0, np.pi / 8)
        for k in range(16):
            ang = base + k * np.pi / 8
            dy, dx = int(round(r * np.sin(ang))), int(round(r * np.cos(ang)))
            ty1, ty2 = max(y1, -dy), min(y2, h - dy)
            tx1, tx2 = max(x1, -dx), min(x2, w - dx)
            if ty1 >= ty2 or tx1 >= tx2:
                continue
            tgt = todo[ty1 - y1:ty2 - y1, tx1 - x1:tx2 - x1]            # a view: edits update `todo`
            if not tgt.any():
                continue
            take = tgt & src_ok[ty1 + dy:ty2 + dy, tx1 + dx:tx2 + dx]
            if not take.any():
                continue
            out[ty1:ty2, tx1:tx2][take] = detail[ty1 + dy:ty2 + dy, tx1 + dx:tx2 + dx][take]
            tgt[take] = False
        r *= 1.25
    return out


def _poisson_blend(filled, crop, mask):
    """Make the fill continue the colour and brightness of the wall / floor around the hole.
    Poisson (gradient-domain) blending keeps the fill's structure but forces its edge to equal the
    real pixels next to it, which removes dark or tinted smears. Falls back to the plain fill."""
    try:
        P = 12
        src = cv2.copyMakeBorder(filled, P, P, P, P, cv2.BORDER_REPLICATE)
        dst = cv2.copyMakeBorder(crop, P, P, P, P, cv2.BORDER_REPLICATE)
        m = cv2.copyMakeBorder(((mask > 127) * 255).astype(np.uint8), P, P, P, P, cv2.BORDER_CONSTANT, value=0)
        ys, xs = np.where(m > 127)
        if len(xs) < 50:
            return filled
        center = (int((xs.min() + xs.max()) // 2), int((ys.min() + ys.max()) // 2))
        out = cv2.seamlessClone(src, dst, m, center, cv2.NORMAL_CLONE)[P:-P, P:-P]
        hole = mask > 127
        if float(np.abs(out.astype(np.int16) - filled.astype(np.int16))[hole].mean()) > 45.0:
            return filled                              # blending went wrong, keep the plain fill
        return out
    except cv2.error:
        return filled


def _restore_detail(filled, crop, mask):
    """Inpainted areas are smoother than a real photo (and LaMa works on a shrunken copy for big
    objects), which reads as 'blurry'. Measure how much fine texture the untouched pixels around
    the object have, and add exactly the missing amount, borrowed from those pixels."""
    hole = mask > 127
    if hole.sum() < 20:
        return filled
    k = max(3, int(0.01 * max(mask.shape)) | 1)
    near = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 127
    src_ok = ~near
    if src_ok.sum() < 400:
        return filled
    sig = 1.6
    g_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g_fill = cv2.cvtColor(filled, cv2.COLOR_BGR2GRAY).astype(np.float32)
    detail = g_crop - cv2.GaussianBlur(g_crop, (0, 0), sig)
    fill_detail = g_fill - cv2.GaussianBlur(g_fill, (0, 0), sig)
    s_out = float(detail[src_ok].std())
    s_fill = float(fill_detail[hole].std())
    need = float(np.sqrt(max(s_out ** 2 - s_fill ** 2, 0.0)))
    if need < 0.4:
        return filled
    need = min(need, 14.0)
    detail = np.clip(detail, -2.5 * s_out, 2.5 * s_out)          # never copy an edge, only fine texture
    borrowed = _borrow_detail(detail, hole, src_ok)
    b_std = float(borrowed[hole].std()) + 1e-6
    add = borrowed / b_std * need
    return np.clip(filled.astype(np.float32) + add[..., None] * hole[..., None], 0, 255).astype(np.uint8)


def _lum(bgr):
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)


def _grow_shadow(crop, m):
    """The dark shadow / contact edge an object leaves on the floor or wall is NOT part of the object,
    so a mask that stops at the object leaves a dark smear for the fill to copy. Add the connected pixels
    next to the mask that are clearly darker than the surroundings."""
    hole = m > 127
    S = max(crop.shape[:2])
    k = max(5, int(0.02 * S) | 1)
    ek = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
    zone = cv2.dilate(m, ek(5 * k)) > 127
    far = zone & ~(cv2.dilate(m, ek(2 * k)) > 127)
    if far.sum() < 200:
        return m
    L = _lum(crop)
    ref = float(np.median(L[far]))
    dark = zone & ~hole & (L < ref - max(8.0, 0.10 * ref))
    cand = (dark | hole).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand)
    keep = np.unique(lab[hole]); keep = keep[keep > 0]
    grown = np.isin(lab, keep) & dark
    if grown.sum() > 2.5 * hole.sum():          # too much growth: probably a dark floor, not a shadow
        return m
    out = ((hole | grown).astype(np.uint8)) * 255
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, ek(k))
    return cv2.dilate(out, ek(max(3, k // 2 | 1)))


def _match_tone(filled, crop, m):
    """If the fill came out darker than the floor / wall around it (the 'black patch'), lift it to match."""
    hole = m > 127
    ring = (cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * max(5, int(0.03 * max(m.shape))) | 1,) * 2)) > 127) & ~hole
    if ring.sum() < 100 or hole.sum() < 50:
        return filled
    ring_m = crop[ring].reshape(-1, 3).mean(0)
    hole_m = filled[hole].reshape(-1, 3).mean(0)
    if hole_m.mean() > 0.9 * ring_m.mean():
        return filled
    gain = np.clip(ring_m / np.maximum(hole_m, 1.0), 1.0, 1.8)
    f = filled.astype(np.float32)
    f[hole] = np.clip(f[hole] * gain, 0, 255)
    return f.astype(np.uint8)


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
        m = _grow_shadow(crop, m)
        filled = _lama_fill(crop, m)
        if filled is None:
            filled, engine = _opencv_fill(crop, m), "opencv"
        filled = _match_tone(filled, crop, m)
        filled = _restore_detail(filled, crop, m)
        k = max(3, int(0.008 * max(H, W)) | 1)
        alpha = cv2.GaussianBlur(m.astype(np.float32) / 255.0, (k, k), 0)[..., None]
        alpha = np.maximum(alpha, (m > 127)[..., None].astype(np.float32))
        blended = crop.astype(np.float32) * (1 - alpha) + filled.astype(np.float32) * alpha
        out[cy1:cy2, cx1:cx2] = np.clip(blended, 0, 255).astype(np.uint8)
    return out, engine

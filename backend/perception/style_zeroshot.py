"""
Room style from the photo WITHOUT any training: CLIP compares the photo with a text
description of each style ("a photo of a scandinavian style interior room") and picks the
closest. It is used only when the trained MobileNetV3 style classifier
(style_mobilenetv3.pt) is not installed, or is not confident.

It needs `transformers` and PyTorch (both already installed for the depth model) and a one-time
download of openai/clip-vit-base-patch32 (about 600 MB). If anything fails it returns None and
the app simply keeps the style neutral. It never raises.
"""

import os

_MODEL_NAME = "openai/clip-vit-base-patch32"
_state = {"model": None, "proc": None, "failed": False, "text": {}}
_cache = {}

_TEMPLATES = (
    "a photo of a {} style interior room",
    "a {} style home interior design",
    "a room decorated in {} style",
)


def _load():
    if _state["failed"]:
        return False
    if _state["model"] is not None:
        return True
    try:
        from transformers import CLIPModel, CLIPProcessor
        print("[style] loading CLIP for zero-shot style detection (first time downloads ~600 MB)...")
        _state["model"] = CLIPModel.from_pretrained(_MODEL_NAME).eval()
        _state["proc"] = CLIPProcessor.from_pretrained(_MODEL_NAME)
        print("[style] CLIP ready")
        return True
    except Exception as e:
        print(f"[style] zero-shot style unavailable: {e}")
        _state["failed"] = True
        return False


def _tensor(x):
    """Different transformers versions return a tensor or an output object."""
    if hasattr(x, "pooler_output") and x.pooler_output is not None:
        return x.pooler_output
    return x


def _text_features(labels, templates=_TEMPLATES):
    import torch
    key = (tuple(labels), tuple(templates))
    if key in _state["text"]:
        return _state["text"][key]
    model, proc = _state["model"], _state["proc"]
    feats = []
    for lab in labels:
        prompts = [t.format(lab) for t in templates]
        inp = proc(text=prompts, return_tensors="pt", padding=True)
        with torch.inference_mode():
            f = _tensor(model.get_text_features(**inp))
        f = f / f.norm(dim=-1, keepdim=True)
        f = f.mean(dim=0)
        feats.append(f / f.norm())
    out = torch.stack(feats)
    _state["text"][key] = out
    return out


def classify_style(image_path, choices, templates=_TEMPLATES):
    """choices: list of (value, label). Returns {"value", "label", "confidence", "ranking"} or None."""
    if not choices:
        return None
    try:
        key = (image_path, os.path.getmtime(image_path), tuple(v for v, _ in choices), tuple(templates))
    except OSError:
        return None
    if key in _cache:
        return _cache[key]
    if not _load():
        return None
    try:
        import torch
        from PIL import Image
        model, proc = _state["model"], _state["proc"]
        img = Image.open(image_path).convert("RGB")
        with torch.inference_mode():
            f = _tensor(model.get_image_features(**proc(images=img, return_tensors="pt")))
            f = f / f.norm(dim=-1, keepdim=True)
            text = _text_features([lab for _, lab in choices], templates)
            probs = (100.0 * f @ text.T).softmax(dim=-1)[0].tolist()
        order = sorted(range(len(choices)), key=lambda i: -probs[i])
        best = order[0]
        result = {
            "value": choices[best][0], "label": choices[best][1], "confidence": round(probs[best], 3),
            "ranking": [{"style": choices[i][1], "p": round(probs[i], 3)} for i in order[:3]],
        }
    except Exception as e:
        print(f"[style] zero-shot failed: {e}")
        return None
    if len(_cache) > 20:
        _cache.clear()
    _cache[key] = result
    return result


# ---- which room is it? ----------------------------------------------------------------------
_ROOMS = [
    ("bedroom", "bedroom"), ("living", "living room"), ("dining", "kitchen or dining room"),
    ("study", "study room or home office"), ("kids", "children's room"), ("outdoor", "balcony or patio"),
]
_ROOM_TEMPLATES = ("a photo of a {}", "an interior photo of a {}", "a {} in a house")


def classify_room(image_path):
    """What kind of room is this photo? Returns {"kind", "confidence", "ranking"} or None.
    Used only when the user chose 'Not sure' and the detected furniture did not settle it."""
    r = classify_style(image_path, _ROOMS, _ROOM_TEMPLATES)
    return None if r is None else {"kind": r["value"], "confidence": r["confidence"], "ranking": r["ranking"]}

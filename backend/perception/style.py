"""
Room-style classifier (MobileNetV3-Small). Train it with train/2_train_style_classifier.ipynb,
then copy the two output files into backend/perception/weights/:
    style_mobilenetv3.pt   style_classes.json
Until they exist this returns ("unclassified", 0.0) and the app asks the user to pick a style.
"""
import json
import os

WEIGHTS = os.path.join(os.path.dirname(__file__), "weights", "style_mobilenetv3.pt")
CLASSES = os.path.join(os.path.dirname(__file__), "weights", "style_classes.json")
_cache = {}


def _load():
    if "m" not in _cache:
        import torch
        from torchvision.models import mobilenet_v3_small
        classes = json.load(open(CLASSES))
        model = mobilenet_v3_small(num_classes=len(classes))
        model.load_state_dict(torch.load(WEIGHTS, map_location="cpu"))
        _cache["m"], _cache["classes"] = model.eval(), classes
    return _cache["m"], _cache["classes"]


def predict_style(image_rgb):
    """image_rgb: HxWx3 uint8 array -> (style label, confidence 0..1)."""
    if not (os.path.exists(WEIGHTS) and os.path.exists(CLASSES)):
        return "unclassified", 0.0
    try:
        import numpy as np
        import torch
        import cv2
        model, classes = _load()
        x = cv2.resize(image_rgb, (224, 224)).astype("float32") / 255.0
        x = (x - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
        x = torch.from_numpy(x.transpose(2, 0, 1)).float().unsqueeze(0)
        with torch.no_grad():
            p = torch.softmax(model(x), 1)[0]
        i = int(p.argmax())
        return str(classes[i]).lower(), round(float(p[i]), 2)
    except Exception as e:
        print(f"[perception.style] skipped: {e}")
        return "unclassified", 0.0

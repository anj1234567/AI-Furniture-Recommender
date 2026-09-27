"""
Track A owns this file.

Contract: see docs/CONTRACTS.md section 1.
Replace analyze_room()'s body with the real pipeline (YOLOv8 detection,
K-means colour extraction, MobileNetV3 style classification). Keep the
function name, signature, and return shape identical so nothing downstream
needs to change.
"""

STYLE_CONFIDENCE_THRESHOLD = 0.6


def analyze_room(image_path: str) -> dict:
    """
    MOCK IMPLEMENTATION — replace with real detection/colour/style pipeline.

    Args:
        image_path: path to the uploaded, pre-processed room photo.

    Returns:
        dict matching docs/CONTRACTS.md section 1.
    """
    style_confidence = 0.83
    return {
        "detections": [
            {"label": "sofa", "bbox": [40, 120, 340, 360], "confidence": 0.91},
            {"label": "coffee_table", "bbox": [150, 300, 280, 380], "confidence": 0.85},
        ],
        "empty_space": [
            {"region": "floor", "bbox": [0, 380, 640, 480], "area_ratio": 0.22},
        ],
        "dominant_colors": ["#E8DCC8", "#4A4A4A", "#B08D57"],
        "style": {"label": "scandinavian", "confidence": style_confidence},
        "needs_confirmation": style_confidence < STYLE_CONFIDENCE_THRESHOLD,
    }

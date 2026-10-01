"""
Which detections count as "the room already has this".

The fine-tuned detector reports 50-65% on furniture that is plainly visible, so a flat 60% cut-off
threw away real sofas and beds. The rule now uses a threshold per furniture type, and a size check
that still rejects a folded mattress or a small patch of floor.
"""

# per catalog category: (minimum confidence, minimum share of the photo the box must cover)
RULES = {
    "bed":   (0.50, 0.10),
    "sofa":  (0.40, 0.05),
    "chair": (0.40, 0.01),
    "table": (0.40, 0.02),
}


def _area(d, W, H):
    x1, y1, x2, y2 = d["bbox"]
    return max(0, x2 - x1) * max(0, y2 - y1) / float(W * H)


def _iou_or_contained(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw, ih = max(0, min(ax2, bx2) - max(ax1, bx1)), max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a, area_b = (ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1)
    return max(inter / (area_a + area_b - inter), inter / max(1.0, min(area_a, area_b)) * 0.9)


def drop_duplicates(dets):
    """One object, one box: when two boxes of the same type overlap a lot, keep the stronger one."""
    keep = []
    for d in sorted(dets, key=lambda d: -float(d.get("confidence", 0))):
        if any(k["label"] == d["label"] and _iou_or_contained(k["bbox"], d["bbox"]) > 0.6 for k in keep):
            continue
        keep.append(d)
    return keep


def recount(dets, to_category, W, H):
    """Re-judge detections the base rule rejected. Only ever turns 'not counted' into 'counted'."""
    for d in dets:
        if d.get("counted"):
            continue
        cat = to_category.get(d["label"])
        if cat not in RULES:
            continue
        min_conf, min_area = RULES[cat]
        if float(d["confidence"]) >= min_conf and _area(d, W, H) >= min_area:
            d["counted"], d["not_counted_reason"] = True, None
    return dets

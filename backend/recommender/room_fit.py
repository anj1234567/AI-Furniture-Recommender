"""
Which furniture belongs in which room.

Two levels:
1. Category level: a kitchen/dining room gets tables and chairs, never a sofa or a bed.
2. Product-type level (from the product name): a bedroom gets a bedside table, not a
   dining table; a dining room gets a dining table, not a nightstand.

Everything here is plain rules on purpose, so it can be explained and tested.
"""

import re

# catalog categories are: bed, sofa, table, chair
ROOM_CATEGORIES = {
    "bedroom": {"bed", "chair", "table"},
    "living":  {"sofa", "chair", "table"},
    "dining":  {"table", "chair"},
    "study":   {"table", "chair"},
    "kids":    {"bed", "chair", "table"},
    "outdoor": {"sofa", "chair", "table"},
}

# words in the dropdown value / label  ->  room kind (checked in this order)
_KIND_WORDS = [
    ("kid", "kids"), ("child", "kids"), ("nursery", "kids"),
    ("bed", "bedroom"), ("master", "bedroom"), ("guest", "bedroom"),
    ("living", "living"), ("lounge", "living"), ("hall", "living"), ("drawing", "living"),
    ("kitchen", "dining"), ("dining", "dining"), ("pantry", "dining"),
    ("study", "study"), ("office", "study"), ("work", "study"),
    ("outdoor", "outdoor"), ("patio", "outdoor"), ("balcony", "outdoor"), ("garden", "outdoor"),
]


def room_kind(room_type):
    """Dropdown value -> 'bedroom' | 'living' | 'dining' | 'study' | 'kids' | 'outdoor' | None."""
    s = str(room_type or "").strip().lower()
    if not s or s in ("any", "none", "not sure", "unknown"):
        return None
    for word, kind in _KIND_WORDS:
        if word in s:
            return kind
    return None


def infer_room_kind(detections, detection_to_category=None):
    """Guess the room from what the detector found (only confident / counted detections).
    A bed means bedroom, a sofa or TV means living room. Otherwise unknown."""
    seen = set()
    for d in detections or []:
        if d.get("counted") or float(d.get("confidence", 0)) >= 0.6:
            seen.add(str(d.get("label", "")).lower())
    if "bed" in seen or "wardrobe" in seen:
        return "bedroom"
    if seen & {"sofa", "couch", "tv"}:
        return "living"
    return None


# ---- product-type rules from the product name ---------------------------------------------
_SMALL_TABLES = ("nightstand", "night stand", "bedside", "end table", "side table", "coffee table",
                 "cocktail", "accent table", "sofa table", "console", "nesting", "tray table")
_DINING_TABLES = ("dining", "kitchen", "bar table", "pub", "counter", "breakfast", "bistro", "farmhouse table")
_BEDSIDE = ("nightstand", "night stand", "bedside", "end table", "side table")
_LOUNGE_CHAIRS = ("accent", "armless", "recliner", "lounge", "club chair", "slipper", "wingback",
                  "armchair", "papasan", "bean bag", "rocker", "glider", "chaise")
_DINING_CHAIRS = ("dining", "bar stool", "counter stool", "barstool", "kitchen", "parsons", "side chair")
_BAR = ("bar stool", "counter stool", "barstool", "bar height")

# per room kind and category: words to avoid ("bad") and words to prefer ("good")
_RULES = {
    "dining":  {"table": {"bad": _SMALL_TABLES, "good": _DINING_TABLES},
                "chair": {"bad": _LOUNGE_CHAIRS, "good": _DINING_CHAIRS}},
    "living":  {"table": {"bad": _DINING_TABLES + ("nightstand", "night stand", "bedside"), "good": ("coffee table", "cocktail", "end table", "side table")},
                "chair": {"bad": _DINING_CHAIRS, "good": _LOUNGE_CHAIRS}},
    "bedroom": {"table": {"bad": _DINING_TABLES + ("coffee table", "cocktail"), "good": _BEDSIDE},
                "chair": {"bad": _DINING_CHAIRS, "good": _LOUNGE_CHAIRS}},
    "study":   {"table": {"bad": _SMALL_TABLES, "good": ("desk", "writing", "work", "study")},
                "chair": {"bad": _BAR + _LOUNGE_CHAIRS[3:], "good": ("desk", "task", "study", "dining")}},
    "kids":    {"table": {"bad": _DINING_TABLES, "good": ("kid", "child", "play", "activity", "study")},
                "chair": {"bad": _BAR, "good": ("kid", "child")}},
}

MIN_LEFT = 3   # never filter a category down to fewer options than this


def _has(name, words):
    n = " " + re.sub(r"[^a-z0-9 ]", " ", str(name).lower()) + " "
    return any(w in n for w in words)


def fit_catalog_to_room(items, kind):
    """Keep the products whose type suits this room. Falls back to the unfiltered list for any
    category where the rules would leave fewer than MIN_LEFT products."""
    rules = _RULES.get(kind)
    if not rules:
        return list(items)
    out = []
    for cat in {str(i.get("category", "")).lower() for i in items}:
        pool = [i for i in items if str(i.get("category", "")).lower() == cat]
        r = rules.get(cat)
        if r:
            ok = [i for i in pool if not _has(i.get("name", ""), r["bad"])]
            if len(ok) >= MIN_LEFT:
                pool = ok
            good = [i for i in pool if _has(i.get("name", ""), r["good"])]
            if len(good) >= MIN_LEFT:
                pool = good
        out.extend(pool)
    return out


# ---- plausible room sizes --------------------------------------------------------------------
# one photo shows only part of a room, so the depth-based size is often too large.
# Real homes keep each room kind inside a normal range; clamp the estimate into it.
_BOUNDS = {            # (min_short, max_short, min_long, max_long) in metres
    "bedroom": (2.6, 4.2, 3.0, 5.0),
    "kids":    (2.4, 3.8, 2.8, 4.5),
    "living":  (3.0, 5.2, 3.6, 6.5),
    "dining":  (2.4, 4.2, 3.0, 5.5),
    "study":   (2.0, 3.6, 2.4, 4.2),
    "outdoor": (2.5, 7.0, 3.0, 9.0),
}
_DEFAULT_BOUNDS = (2.4, 5.5, 3.0, 7.0)


def plausible_room(width_m, length_m, kind):
    """Clamp an estimated size into a normal range for the room kind. Returns (w, l, changed)."""
    lo_s, hi_s, lo_l, hi_l = _BOUNDS.get(kind, _DEFAULT_BOUNDS)
    short, long_ = sorted((float(width_m), float(length_m)))
    s2 = min(max(short, lo_s), hi_s)
    l2 = min(max(long_, lo_l), hi_l)
    if width_m <= length_m:
        w2, len2 = s2, l2
    else:
        w2, len2 = l2, s2
    w2, len2 = round(w2, 1), round(len2, 1)
    return w2, len2, (abs(w2 - width_m) > 0.05 or abs(len2 - length_m) > 0.05)

"""
Track B owns this file.

REAL implementation (v1): Multi-Choice Knapsack Problem (MCKP) solved via
Dynamic Programming, plus a Greedy baseline for the Phase 3 comparison your
synopsis's Scalability Analysis section calls for.

Rule: pick AT MOST ONE item per category, maximise total compatibility
score, subject to total price <= budget.

Scoring (rule-based, matches the Explainability layer's simplicity):
- style_score = 1.0 if the item's style_tags include the detected style,
  else 0.2. If style is "unclassified" (perception hasn't trained a real
  classifier yet), style_score is neutral (0.5) for every item, so the
  optimizer falls back to optimizing on colour + budget alone -- still a
  real, working algorithm, just without the style signal yet.
- color_score = how close the item's colours are to the colours found in the
  room photo (continuous 0..1, RGB distance).
- room_score = 1.0 if the item's room_type suits the room type the user
  picked, else 0.2. Neutral (0.5) if the user didn't pick one. It is a soft
  bonus, not a filter, because the catalog doesn't have every category for
  every room type.
- style can come from the user's pick (see STYLE_GROUPS) until the trained
  style classifier exists.
- total = 0.45 * style_score + 0.35 * color_score + 0.20 * room_score
"""

from typing import List, Dict, Optional

# Small named-colour reference palette for mapping detected hex codes to
# names that match the catalog's color_tags vocabulary (e.g. "beige", "gold").
# Extend this list if your catalog uses more colour names.
_NAMED_COLORS = {
    # neutrals
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "silver": (192, 192, 192), "charcoal": (54, 69, 79), "slate": (112, 128, 144),
    "ivory": (255, 255, 240), "cream": (255, 253, 208), "beige": (232, 220, 200),
    "taupe": (139, 133, 137), "sand": (194, 178, 128), "tan": (210, 180, 140), "khaki": (195, 176, 145),
    # browns / woods
    "brown": (101, 67, 33), "walnut": (94, 63, 45), "oak": (188, 152, 98), "espresso": (60, 36, 21),
    "mahogany": (103, 40, 24), "chocolate": (92, 51, 23), "natural": (222, 184, 135),
    "wood": (160, 120, 80), "teak": (176, 129, 74), "copper": (184, 115, 51), "bronze": (150, 105, 55),
    "rust": (183, 65, 14), "terracotta": (204, 100, 70),
    # metals / warm
    "gold": (176, 141, 87), "mustard": (218, 165, 32), "yellow": (218, 165, 32),
    "orange": (210, 105, 30),
    # colours
    "navy": (0, 0, 128), "blue": (65, 105, 225), "teal": (0, 128, 128), "turquoise": (64, 224, 208),
    "green": (34, 139, 34), "olive": (107, 142, 35), "sage": (156, 175, 136), "mint": (152, 200, 170),
    "emerald": (20, 130, 90), "red": (178, 34, 34), "maroon": (128, 0, 0), "burgundy": (128, 0, 32),
    "coral": (240, 128, 110), "pink": (255, 182, 193), "purple": (102, 51, 153), "lavender": (180, 160, 220),
    # extra names found in the real catalog
    "amber": (255, 191, 0), "ash": (178, 190, 181), "azure": (0, 127, 255), "blush": (222, 159, 171),
    "brass": (181, 166, 66), "chrome": (200, 200, 205), "cognac": (154, 70, 30), "concrete": (149, 149, 149),
    "crimson": (220, 20, 60), "crystal": (220, 235, 240), "graphite": (56, 56, 60), "marble": (235, 235, 232),
    "mauve": (176, 131, 153), "obsidian": (20, 20, 25), "ochre": (204, 119, 34), "onyx": (53, 56, 57),
    "pearl": (234, 224, 200), "plum": (142, 69, 133), "ruby": (155, 17, 30), "sapphire": (15, 82, 186),
    "steel": (110, 120, 130), "terra": (204, 100, 70), "titanium": (135, 134, 129),
}


# ---------------------------------------------------------------------------
# User-selectable style and room type.
# The catalog has 37 fine-grained style tags (nordic, minimal, deco, ...).
# The user picks a broad style; each broad style groups the catalog tags
# that belong to it. Until the style classifier is trained, this pick is
# where the room style comes from.
# ---------------------------------------------------------------------------
STYLE_GROUPS = {
    "modern": {"modern", "minimal", "minimalist", "streamline", "futuristic", "hightech"},
    "scandinavian": {"scandinavian", "nordic", "minimal", "minimalist"},
    "industrial": {"industrial", "brutalist", "hightech", "architectural"},
    "bohemian": {"bohemian", "eclectic", "organic", "biomorphic"},
    "traditional": {"traditional", "classic", "classical", "victorian", "baroque", "colonial", "provincial", "gothic"},
    "coastal": {"coastal", "organic"},
    "rustic": {"rustic", "primitive", "provincial"},
    "japanese": {"japanese", "zen", "minimal", "minimalist"},
    "retro": {"retro", "deco", "postmodern", "bauhaus", "italian"},
}

# Broad room type -> catalog room_type values that suit it.
ROOM_GROUPS = {
    "bedroom": {"master", "bedroom", "guest", "suite", "dorm", "loft", "studio"},
    "living": {"living", "lounge", "theater", "penthouse", "lobby", "library", "vacation"},
    "dining": {"dining", "kitchen", "cafe"},
    "study": {"study", "office", "library", "conference", "gaming"},
    "kids": {"kids", "nursery"},
    "outdoor": {"outdoor", "vacation"},
}

STYLE_OPTIONS = [{"value": k, "label": k.title()} for k in STYLE_GROUPS]
ROOM_OPTIONS = [
    {"value": "bedroom", "label": "Bedroom"},
    {"value": "living", "label": "Living room"},
    {"value": "dining", "label": "Dining / Kitchen"},
    {"value": "study", "label": "Study / Office"},
    {"value": "kids", "label": "Kids room"},
    {"value": "outdoor", "label": "Outdoor"},
]


MAX_ALTERNATIVES = 3  # swap options shown per category


def _no_choice(value) -> bool:
    return value is None or str(value).strip().lower() in ("", "unclassified", "auto", "any")


def style_matches(item: Dict, style: str) -> bool:
    """True if the item's style tags belong to the chosen style."""
    tags = {t.lower() for t in item.get("style_tags", [])}
    s = str(style).strip().lower()
    return bool(tags & STYLE_GROUPS.get(s, {s}))


def room_matches(item: Dict, room_type: str) -> bool:
    """True if the item's catalog room_type suits the chosen room type."""
    rt = str(item.get("room_type") or "").lower()
    r = str(room_type).strip().lower()
    return rt in ROOM_GROUPS.get(r, {r})


def _hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _nearest_color_name(hex_color: str) -> str:
    r1, g1, b1 = _hex_to_rgb(hex_color)
    best_name, best_dist = None, float("inf")
    for name, (r2, g2, b2) in _NAMED_COLORS.items():
        dist = (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name


def _color_score(color_tags: List[str], palette_rgb: List[tuple]) -> float:
    """Continuous 0..1 colour match: how close each of the item's colours is
    to the nearest colour actually found in the room photo (RGB distance)."""
    if not color_tags or not palette_rgb:
        return 0.3  # neutral
    scores = []
    for tag in color_tags:
        ref = _NAMED_COLORS.get(tag.lower())
        if ref is None:
            scores.append(0.3)
            continue
        nearest = min(
            ((ref[0] - r) ** 2 + (ref[1] - g) ** 2 + (ref[2] - b) ** 2) ** 0.5
            for (r, g, b) in palette_rgb
        )
        scores.append(max(0.0, 1 - nearest / 200))
    return sum(scores) / len(scores)


def _score_item(item: Dict, style: str, palette_rgb: List[tuple], room_type: Optional[str] = None) -> float:
    style_score = 0.5 if _no_choice(style) else (1.0 if style_matches(item, style) else 0.2)
    room_score = 0.5 if _no_choice(room_type) else (1.0 if room_matches(item, room_type) else 0.2)
    color_score = _color_score(item.get("color_tags", []), palette_rgb)
    return round(0.45 * style_score + 0.35 * color_score + 0.2 * room_score, 3)


def _group_by_category(catalog: List[Dict]) -> Dict[str, List[Dict]]:
    groups: Dict[str, List[Dict]] = {}
    for item in catalog:
        groups.setdefault(item["category"], []).append(item)
    return groups


def solve_dp(items_by_category: Dict[str, List[Dict]], budget: float) -> List[Dict]:
    """
    Real MCKP solved via Dynamic Programming.
    dp[b] = best total score achievable spending at most b, after
    considering categories processed so far. choice[i][b] records which
    item (or none) was picked for category i at budget b, for backtracking.

    Budget is treated as an integer (rupees) for the DP table -- fine for
    catalog prices in this range; round to a coarser unit (e.g. //10) first
    if you need this faster on a much larger catalog.
    """
    from math import gcd
    from functools import reduce

    budget = int(budget)
    categories = list(items_by_category.keys())
    n = len(categories)

    # Exact speed-up: all prices are multiples of their gcd (e.g. 1000), so
    # the DP table can count in that unit. Within one category, only the
    # best-scoring item at each price can ever matter.
    prices = [int(it["price"]) for items in items_by_category.values() for it in items]
    unit = reduce(gcd, prices) if prices else 1
    unit = max(unit, 1)
    cap = budget // unit
    reduced = {}
    for cat in categories:
        best = {}
        for item in items_by_category[cat]:
            p = int(item["price"]) // unit
            if p not in best or item["_score"] > best[p]["_score"]:
                best[p] = item
        reduced[cat] = list(best.items())  # (price_in_units, item)

    dp = [[0.0] * (cap + 1) for _ in range(n + 1)]
    choice = [[None] * (cap + 1) for _ in range(n + 1)]

    for i, cat in enumerate(categories, start=1):
        for b in range(cap + 1):
            dp[i][b] = dp[i - 1][b]  # option: skip this category entirely
            choice[i][b] = None
            for price, item in reduced[cat]:
                if price <= b:
                    # tiny price penalty: among equal scores, prefer the cheaper option
                    candidate = dp[i - 1][b - price] + item["_score"] - price * unit * 1e-9
                    if candidate > dp[i][b]:
                        dp[i][b] = candidate
                        choice[i][b] = (price, item)

    # Backtrack to recover the selected items
    selected = []
    b = cap
    for i in range(n, 0, -1):
        picked = choice[i][b]
        if picked is not None:
            price, item = picked
            selected.append(item)
            b -= price
    return selected


def solve_greedy(items_by_category: Dict[str, List[Dict]], budget: float) -> List[Dict]:
    """Greedy baseline: sort ALL items (across every category) by
    score-per-rupee descending, take each one if it fits the remaining
    budget and its category hasn't been filled yet."""
    all_items = [item for items in items_by_category.values() for item in items]
    all_items.sort(key=lambda it: it["_score"] / max(it["price"], 1), reverse=True)

    selected, filled_categories, remaining = [], set(), budget
    for item in all_items:
        if item["category"] in filled_categories:
            continue
        if item["price"] <= remaining:
            selected.append(item)
            filled_categories.add(item["category"])
            remaining -= item["price"]
    return selected


def recommend(
    style: str,
    palette: List[str],
    budget: float,
    catalog: List[Dict],
    method: str = "dp_optimal",
    room_type: Optional[str] = None,
) -> dict:
    """
    Real recommender. See docs/CONTRACTS.md section 3 for the return shape.

    Args:
        style: detected room style label ("unclassified" until Perception's
               style classifier is trained -- handled gracefully, see module docstring).
        palette: list of dominant hex colours from the perception layer.
        budget: user's total stated budget.
        catalog: list of catalog items (docs/CONTRACTS.md section 2).
        method: "dp_optimal" (default) or "greedy" -- for the Phase 3 comparison.
        room_type: optional broad room type picked by the user (see ROOM_GROUPS).
    """
    if not catalog:
        return {"selected_items": [], "total_price": 0, "compatibility_score": 0, "method": method}

    palette_rgb = [_hex_to_rgb(hexc) for hexc in palette]

    # Score every item once up front (both solvers reuse "_score")
    scored_catalog = []
    for item in catalog:
        item = dict(item)  # don't mutate the caller's catalog
        item["_score"] = _score_item(item, style, palette_rgb, room_type)
        scored_catalog.append(item)

    items_by_category = _group_by_category(scored_catalog)

    solver = solve_dp if method == "dp_optimal" else solve_greedy
    picked = solver(items_by_category, budget)

    selected_items = [
        {"item_id": it["id"], "category": it["category"], "score": it["_score"], "price": it["price"]}
        for it in picked
    ]
    total_price = sum(it["price"] for it in selected_items)
    avg_score = round(sum(it["score"] for it in selected_items) / len(selected_items), 3) if selected_items else 0

    # Top alternatives per chosen category, so the user can swap an item.
    # Only items that individually fit the budget; near-duplicate names skipped.
    alternatives = {}
    for sel in picked:
        cat = sel["category"]
        pool = sorted(
            (it for it in items_by_category[cat] if it["id"] != sel["id"] and it["price"] <= budget),
            key=lambda it: (-it["_score"], it["price"]),
        )
        seen, alts = {sel.get("name")}, []
        for it in pool:
            if it.get("name") in seen:
                continue
            seen.add(it.get("name"))
            alts.append({"item_id": it["id"], "category": cat, "score": it["_score"], "price": it["price"]})
            if len(alts) == MAX_ALTERNATIVES:
                break
        alternatives[cat] = alts

    return {
        "selected_items": selected_items,
        "alternatives": alternatives,
        "total_price": total_price,
        "compatibility_score": avg_score,
        "method": method,
    }


# ---------------------------------------------------------------------------
# Gap analysis: use what perception detected to avoid recommending furniture
# the room already has.
# ---------------------------------------------------------------------------

# COCO/YOLO label -> catalog category name
DETECTION_TO_CATEGORY = {
    "chair": "chair",
    "couch": "sofa",
    "bed": "bed",
    "dining table": "table",
}


MIN_DETECTION_CONFIDENCE = 0.6  # below this, a detection is treated as uncertain

# Large furniture must cover a reasonable share of the photo to count as "the room
# has one". Small boxes are usually folded mattresses, cushions or bedding.
# Heuristic: the real fix is fine-tuning the detector (final phase).
MIN_AREA_RATIO = {"bed": 0.10, "sofa": 0.08}


def classify_detection(d: Dict):
    """Returns (counted, reason). counted=True means 'the room already has this'."""
    category = DETECTION_TO_CATEGORY.get(d["label"])
    if category is None:
        return False, "not a catalog category"
    if d["confidence"] < MIN_DETECTION_CONFIDENCE:
        return False, "low confidence"
    if d.get("area_ratio", 1.0) < MIN_AREA_RATIO.get(category, 0.0):
        return False, f"too small to be a full {category}"
    return True, None


def find_missing_categories(catalog: List[Dict], detections: List[Dict]) -> List[str]:
    """Catalog categories the detector did NOT reliably find in the room."""
    present = {
        DETECTION_TO_CATEGORY[d["label"]]
        for d in detections
        if classify_detection(d)[0]
    }
    all_categories = {item["category"].lower() for item in catalog}
    return sorted(all_categories - present)


def filter_to_missing(catalog: List[Dict], missing: List[str]) -> List[Dict]:
    """Keep only items whose category the room is missing. If the room already
    has everything in the catalog, return the full catalog (upgrade mode)."""
    if not missing:
        return catalog
    return [item for item in catalog if item["category"].lower() in missing]


def unmapped_colors(catalog: List[Dict]) -> List[str]:
    """Colour names in the catalog that are missing from _NAMED_COLORS.
    Items with such colours can only get a neutral colour score."""
    names = {tag.lower() for item in catalog for tag in item.get("color_tags", [])}
    return sorted(names - set(_NAMED_COLORS))


def matching_colors(color_tags: List[str], palette_hex: List[str], max_dist: float = 90) -> List[str]:
    """Item colours that are visibly close to a colour found in the room
    (same distance measure the scorer uses, so explanations match the scores)."""
    palette_rgb = [_hex_to_rgb(h) for h in palette_hex]
    matched = []
    for tag in color_tags:
        ref = _NAMED_COLORS.get(tag.lower())
        if ref is None:
            continue
        nearest = min(
            ((ref[0] - r) ** 2 + (ref[1] - g) ** 2 + (ref[2] - b) ** 2) ** 0.5
            for (r, g, b) in palette_rgb
        ) if palette_rgb else 999
        if nearest <= max_dist:
            matched.append(tag)
    return matched

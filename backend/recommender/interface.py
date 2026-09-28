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
- color_score = fraction of the item's color_tags that appear in the
  room's dominant colours (mapped from hex to named colours).
- total = 0.6 * style_score + 0.4 * color_score
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
}


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


def _score_item(item: Dict, style: str, palette_rgb: List[tuple]) -> float:
    if style == "unclassified":
        style_score = 0.5
    else:
        tags = [t.lower() for t in item.get("style_tags", [])]
        style_score = 1.0 if style.lower() in tags else 0.2

    color_score = _color_score(item.get("color_tags", []), palette_rgb)
    return round(0.6 * style_score + 0.4 * color_score, 3)


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
    budget = int(budget)
    categories = list(items_by_category.keys())
    n = len(categories)

    dp = [[0.0] * (budget + 1) for _ in range(n + 1)]
    choice = [[None] * (budget + 1) for _ in range(n + 1)]

    for i, cat in enumerate(categories, start=1):
        items = items_by_category[cat]
        for b in range(budget + 1):
            dp[i][b] = dp[i - 1][b]  # option: skip this category entirely
            choice[i][b] = None
            for item in items:
                price = int(item["price"])
                if price <= b:
                    # tiny price penalty: among equal scores, prefer the cheaper option
                    candidate = dp[i - 1][b - price] + item["_score"] - price * 1e-9
                    if candidate > dp[i][b]:
                        dp[i][b] = candidate
                        choice[i][b] = item

    # Backtrack to recover the selected items
    selected = []
    b = budget
    for i in range(n, 0, -1):
        picked = choice[i][b]
        if picked is not None:
            selected.append(picked)
            b -= int(picked["price"])
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
    """
    if not catalog:
        return {"selected_items": [], "total_price": 0, "compatibility_score": 0, "method": method}

    palette_rgb = [_hex_to_rgb(hexc) for hexc in palette]

    # Score every item once up front (both solvers reuse "_score")
    scored_catalog = []
    for item in catalog:
        item = dict(item)  # don't mutate the caller's catalog
        item["_score"] = _score_item(item, style, palette_rgb)
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

    return {
        "selected_items": selected_items,
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


def find_missing_categories(catalog: List[Dict], detections: List[Dict],
                            min_confidence: float = MIN_DETECTION_CONFIDENCE) -> List[str]:
    """Catalog categories that the detector did NOT confidently find in the room.
    Low-confidence detections (e.g. a mattress the COCO model calls a 'bed' at
    54%) don't count as 'the room already has this'."""
    present = {
        DETECTION_TO_CATEGORY[d["label"]]
        for d in detections
        if d["label"] in DETECTION_TO_CATEGORY and d["confidence"] >= min_confidence
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

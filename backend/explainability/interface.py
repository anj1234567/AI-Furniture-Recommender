"""
Track B owns this file.

Rule-based explanations built from the real signals the recommender used:
gap in the room, style match, colour match, and share of budget.
"""

from typing import Dict
from recommender.interface import matching_colors


def explain(item: Dict, room_context: Dict) -> str:
    """
    Args:
        item: selected item merged with its catalog record
              (category, price, score, style_tags, color_tags).
        room_context: {"style", "dominant_colors", "budget", "missing_categories"}

    Returns:
        One human-readable sentence built from the real match signals.
    """
    reasons = []
    category = item.get("category", "item")

    if category.lower() in room_context.get("missing_categories", []):
        reasons.append(f"your room has no {category} yet")

    style = room_context.get("style", "unclassified")
    style_tags = [t.lower() for t in item.get("style_tags", [])]
    if style != "unclassified" and style.lower() in style_tags:
        reasons.append(f"its {style} style matches your room")

    matched = matching_colors(item.get("color_tags", []), room_context.get("dominant_colors", []))
    if matched:
        reasons.append(f"its {', '.join(matched)} colour matches your room's palette")

    budget = room_context.get("budget") or 0
    price = item.get("price", 0)
    if budget > 0:
        reasons.append(f"it costs \u20b9{int(price)}, {round(100 * price / budget)}% of your budget")

    return "Recommended because " + "; ".join(reasons) + "."

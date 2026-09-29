"""
Track B owns this file.

Rule-based explanations built from the real signals the recommender used:
gap in the room, style match, colour match, and share of budget.
"""

from typing import Dict
from recommender.interface import matching_colors, style_matches, room_matches, _no_choice


def explain(item: Dict, room_context: Dict) -> str:
    """
    Args:
        item: selected item merged with its catalog record
              (category, price, score, style_tags, color_tags).
        room_context: {"style", "dominant_colors", "budget", "missing_categories", "room_type"}

    Returns:
        One human-readable sentence built from the real match signals.
    """
    reasons = []
    category = item.get("category", "item")

    if category.lower() in room_context.get("missing_categories", []):
        reasons.append(f"your room has no {category} yet")

    style = room_context.get("style", "unclassified")
    if not _no_choice(style) and style_matches(item, style):
        reasons.append(f"its {', '.join(item.get('style_tags', []))} style matches your {style} room")

    room_type = room_context.get("room_type")
    if not _no_choice(room_type) and room_matches(item, room_type):
        reasons.append(f"it is designed for a {item.get('room_type')} space, which suits your {room_type}")

    matched = matching_colors(item.get("color_tags", []), room_context.get("dominant_colors", []))
    if matched:
        reasons.append(f"its {', '.join(matched)} colour matches your room's palette")

    budget = room_context.get("budget") or 0
    price = item.get("price", 0)
    if budget > 0:
        reasons.append(f"it costs \u20b9{int(price)}, {round(100 * price / budget)}% of your budget")

    return "Recommended because " + "; ".join(reasons) + "."

"""
Track B owns this file.

Contract: see docs/CONTRACTS.md section 3.

Real implementation: either a rule-based template over the same features used
in recommender scoring (colour match, style match, space fit, budget fit), or
a lightweight LLM call constrained to those same features. Rule-based is
simpler to demo reliably for a review — start there.
"""

from typing import Dict


def explain(item: Dict, room_context: Dict) -> str:
    """
    MOCK IMPLEMENTATION — replace with rule-based template or constrained LLM call.

    Args:
        item: one entry from recommender.recommend()'s selected_items, merged
              with its full catalog record (name, style_tags, color_tags, price).
        room_context: {"style": ..., "dominant_colors": [...], "budget": ...}
              — the perception output plus the user's stated budget.

    Returns:
        A single short human-readable sentence.
    """
    return (
        f"Selected for its match with your room's {room_context.get('style', 'detected')} "
        f"style and colour palette, and it fits within your remaining budget."
    )

"""
Style filter: if the user picks a style, only furniture in that style is suggested.

Uses the same style groups as the scorer (recommender/interface.py: STYLE_GROUPS), so the filter and
the match score always agree. Untagged items (style-neutral) fill a category that has too few matches.
An item tagged with a DIFFERENT style is never added. A category with nothing at all is reported
instead of silently showing the wrong style.
"""
from recommender.interface import style_matches

MIN_PER_CATEGORY = 3


def _tagged(item):
    return bool(item.get("style_tags"))


def filter_by_style(items, style):
    """Returns (filtered_items, info). Style empty / unclassified -> unchanged, info None."""
    s = str(style or "").strip().lower()
    if s in ("", "unclassified", "any", "none", "not sure", "auto", "unknown"):
        return list(items), None
    out, per_cat, fallback, cats = [], {}, [], []
    for i in items:
        c = str(i.get("category", "")).lower()
        if c not in cats:
            cats.append(c)
    for c in cats:
        pool = [i for i in items if str(i.get("category", "")).lower() == c]
        good = [i for i in pool if style_matches(i, s)]
        neutral = [i for i in pool if not _tagged(i)]
        chosen = good if len(good) >= MIN_PER_CATEGORY else good + neutral
        if not chosen:
            fallback.append(c)
            chosen = pool
        per_cat[c] = {"matching": len(good), "shown": len(chosen)}
        out.extend(chosen)
    return out, {"style": s, "per_category": per_cat, "fallback_categories": fallback}

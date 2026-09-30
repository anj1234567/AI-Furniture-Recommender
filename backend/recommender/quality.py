"""
Keeps only items that make sense as home furniture for the category they are filed under.
The Amazon catalog mixes in folding tables, bookshelves, office chairs, sofa components,
bed foundations, cots and so on; those are removed here, when the catalog is loaded.
Sizes are also sanity-checked, because some listings have wrong dimensions.
"""
import re

JUNK = {
    "all": r"folding|foldable|adjustable height|height adjustable|commercial|banquet|outdoor|patio|"
           r"kids?\b|child|baby|toddler|crib|\bcot\b|component|replacement|cover|cushion set|\bpet\b",
    "bed": r"foundation|box spring|mattress|topper|trundle|loft|bunk|futon|sofa cum bed|daybed|headboard only",
    "table": r"bookshelf|bookcase|shelving|shelf unit|tv unit|tv stand|media|console|laptop|bedside|beside|nightstand|"
             r"desk|stool|bar table|tray|cart",
    "chair": r"office|desk chair|task|gaming|stool|zero gravity|ottoman|sleeper|sectional|bench|rocking|high chair",
    "sofa": r"sofa cum bed|futon|sleeper|component|ottoman|chaise only",
}

# (min, max) in cm; None = no limit
LIMITS = {
    "bed":   {"w": (90, 260),  "d": (150, 260), "h": (20, 200)},
    "sofa":  {"w": (140, 350), "d": (65, 130),  "h": (55, 120)},
    "table": {"w": (40, 280),  "d": (35, 130),  "h": (25, 120)},
    "chair": {"w": (40, 120),  "d": (40, 110),  "h": (60, 130)},
}


def _dims_ok(item):
    lim = LIMITS.get(item["category"])
    if not lim:
        return True
    w, d, h = item.get("width_cm"), item.get("depth_cm"), item.get("height_cm")
    # the catalog stores (width, depth); beds are listed long side first, so accept either order
    for (a, b) in ((w, d), (d, w)) if item["category"] == "bed" else ((w, d),):
        if a is None or b is None:
            continue
        if lim["w"][0] <= a <= lim["w"][1] and lim["d"][0] <= b <= lim["d"][1]:
            break
    else:
        return False if (w and d) else True
    return h is None or lim["h"][0] <= h <= lim["h"][1]


def clean_catalog(catalog):
    kept, dropped = [], 0
    for it in catalog:
        name = (it.get("name") or "").lower()
        bad = re.search(JUNK["all"], name) or re.search(JUNK.get(it["category"], "$^"), name)
        if bad or not _dims_ok(it):
            dropped += 1
            continue
        kept.append(it)
    return kept, dropped

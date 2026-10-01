import json, os, re, time
from pathlib import Path
import requests

API_URL = "https://api.quickcommerceapi.com/v1/search"
CACHE_FILE = Path(__file__).with_name("cache.json")
CACHE_TTL = 7 * 24 * 3600          # keep results for 7 days to save credits
LAT, LON = 12.9021, 77.6639        # placeholder from their example; use one fixed location

_DIMS = re.compile(
    r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(cm|mm|in|inch|inches)\b",
    re.I,
)
_TO_CM = {"cm": 1, "mm": 0.1, "in": 2.54, "inch": 2.54, "inches": 2.54}


def parse_dims_cm(text):
    """Find '150 x 60 x 75 cm' in a product name. Returns None if not found."""
    m = _DIMS.search(text or "")
    if not m:
        return None
    f = _TO_CM[m.group(4).lower()]
    a, b, c = (round(float(m.group(i)) * f, 1) for i in (1, 2, 3))
    return {"a_cm": a, "b_cm": b, "c_cm": c}   # order is as written, not guaranteed W x D x H


def _normalize(p, category):
    images = p.get("images") or []
    return {
        "id": f"online_{p.get('id')}",
        "source": "online",
        "category": category,
        "name": p.get("name"),
        "brand": p.get("brand"),
        "price": p.get("offer_price"),
        "mrp": p.get("mrp"),
        "rating": p.get("rating"),
        "available": p.get("available", True),
        "image": images[0] if images else None,
        "buy_url": p.get("deeplink"),
        "dims": parse_dims_cm(p.get("name", "")),   # None = size not listed
    }


def _load_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def search_online(query, category):
    key = f"{category}|{query}".lower()
    cache = _load_cache()
    hit = cache.get(key)
    if hit and time.time() - hit["t"] < CACHE_TTL:
        return hit["items"]

    api_key = os.environ.get("QC_API_KEY")
    if not api_key:
        raise RuntimeError("QC_API_KEY is not set")

    r = requests.get(
        API_URL,
        headers={"X-API-Key": api_key},
        params={"q": query, "lat": LAT, "lon": LON, "platform": "Amazon"},
        timeout=20,
    )
    r.raise_for_status()
    products = (r.json().get("data") or {}).get("products") or []
    items = [_normalize(p, category) for p in products]

    cache[key] = {"t": time.time(), "items": items}
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return items

# --- relevance filter + ranking -------------------------------------------
OUTDOOR = ["garden", "patio", "outdoor", "balcony"]
COMMON_BAD = [
    "cover", "protector", "replacement", "spare part", "cleaner", "pump",
    "repair", "sticker", "miniature", "dollhouse", "wallpaper",
]
CATEGORY_RULES = {
    "sofa":  {"must": ["sofa", "couch", "settee", "loveseat"],
              "bad": ["inflatable", "bean bag", "lounger", "sofa table", "sofa stand"]},
    "table": {"must": ["table", "desk"],
              "bad": ["tablecloth", "table cloth", "table runner", "table lamp",
                      "table fan", "table tennis"]},
    "chair": {"must": ["chair"],
              "bad": ["chair pad", "chair mat", "wheel", "caster"]},
    "bed":   {"must": ["bed", "cot"],
              "bad": ["bedsheet", "bed sheet", "bedding", "bedside", "bed tray",
                      "bed table", "mattress topper"]},
}

# (category, words in the pick's title, search phrase, words a result must contain)
SUBTYPES = [
    ("table", ["chest of drawers", "dresser", "tallboy"], "chest of drawers", ["drawer", "dresser", "tallboy"]),
    ("table", ["nightstand", "night stand", "bedside"], "bedside table", ["nightstand", "night stand", "bedside"]),
    ("table", ["coffee table", "centre table", "center table"], "coffee table", ["coffee table", "centre table", "center table"]),
    ("table", ["console table"], "console table", ["console"]),
    ("table", ["end table", "side table"], "side table", ["end table", "side table"]),
    ("table", ["dining table"], "dining table", ["dining table"]),
    ("table", ["study table", "writing desk", "desk"], "study table", ["desk", "study table"]),
    ("table", ["drawer"], "chest of drawers", ["drawer", "dresser", "tallboy"]),
    ("chair", ["recliner"], "recliner chair", ["recliner"]),
    ("chair", ["dining chair"], "dining chair", ["dining chair"]),
    ("chair", ["accent chair", "armchair", "arm chair", "club chair"], "accent chair",
     ["accent chair", "armchair", "arm chair", "club chair"]),
    ("sofa", ["loveseat", "love seat", "settee"], "loveseat sofa", ["loveseat", "love seat", "settee", "2 seater"]),
    ("sofa", ["sectional", "l shape", "l-shape"], "l shape sofa", ["sectional", "l shape", "l-shape", "l shaped"]),
    ("sofa", ["sofa bed", "futon", "sleeper"], "sofa cum bed", ["sofa cum bed", "sofa bed", "futon", "sleeper"]),
    ("bed", ["platform bed", "bed frame"], "bed frame", ["bed"]),
]

COLOR_WORDS = ["white", "black", "grey", "gray", "beige", "cream", "ivory", "brown", "tan",
               "walnut", "oak", "teal", "navy", "blue", "green", "red", "yellow", "pink",
               "orange", "silver", "gold", "charcoal"]

# room key -> (words that suit the room, words that suit another room)
ROOM_WORDS = {
    "living":  (["living room"], ["bedroom", "dining", "kitchen", "office", "gaming", "kids", "nursery"]),
    "bedroom": (["bedroom", "bedside"], ["dining", "kitchen", "office", "gaming", "living room"]),
    "dining":  (["dining", "kitchen"], ["bedroom", "office", "gaming", "living room"]),
    "office":  (["office", "study"], ["bedroom", "dining", "living room"]),
    "outdoor": (["outdoor", "garden", "patio", "balcony"], []),
}

_STOP = {"for", "and", "with", "the", "set", "of", "in", "a", "to", "by", "home", "living",
         "room", "furniture", "modern", "premium", "solid"}


def _words(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


def room_key(room_type):
    r = (room_type or "").lower()
    if "liv" in r: return "living"
    if "bed" in r: return "bedroom"
    if "din" in r or "kitchen" in r: return "dining"
    if "office" in r or "study" in r: return "office"
    if "out" in r: return "outdoor"
    return None


def detect_color(name, fallback=""):
    n = (name or "").lower()
    for c in COLOR_WORDS:
        if re.search(rf"\b{c}\b", n):
            return c
    return (fallback or "").lower()


def detect_subtype(name, category):
    n = (name or "").lower()
    for cat, keys, phrase, must in SUBTYPES:
        if cat == category and any(k in n for k in keys):
            return phrase, must
    return None, None


def build_query(ref_name, category, ref_color=""):
    phrase, _ = detect_subtype(ref_name, category)
    color = detect_color(ref_name, ref_color)
    return " ".join(x for x in [color, phrase or category] if x)


def _is_relevant(item, category, must=None, room=None):
    name = (item.get("name") or "").lower()
    rules = CATEGORY_RULES.get(category, {})
    bad = COMMON_BAD + rules.get("bad", [])
    if room != "outdoor":
        bad = bad + OUTDOOR
    if must:
        if not any(w in name for w in must):
            return False
    else:
        need = rules.get("must", [category])
        if not any(re.search(rf"\b{re.escape(w)}s?\b", name) for w in need):
            return False
    return not any(w in name for w in bad)


def pick_best(items, category, ref_price=None, ref_name="", ref_color="", room_type="", limit=4):
    must = detect_subtype(ref_name, category)[1]
    room = room_key(room_type)

    def keep(must_words):
        seen, out = set(), []
        for i in items:
            if not i.get("available", True) or not _is_relevant(i, category, must_words, room):
                continue
            key = (i.get("name") or "").lower()[:40]
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
        return out

    good = keep(must)
    if len(good) < 2 and must:      # too few exact matches: relax to the category (no extra API call)
        good = keep(None)

    ref_words = _words(ref_name)
    suits, clashes = ROOM_WORDS.get(room, ([], []))

    def score(i):
        name = (i.get("name") or "").lower()
        s = 0.1 * ((i.get("rating") or 0) / 5)
        s += 0.05 if i.get("dims") else 0
        if ref_price and i.get("price"):
            s += 0.25 * (1 - min(abs(i["price"] - ref_price) / ref_price, 1))
        w = _words(i.get("name"))
        if ref_words and w:
            s += 0.35 * len(ref_words & w) / len(ref_words | w)
        if ref_color and ref_color in name:
            s += 0.1
        if any(k in name for k in suits):
            s += 0.1
        if any(k in name for k in clashes):
            s -= 0.2
        return s

    return sorted(good, key=score, reverse=True)[:limit]
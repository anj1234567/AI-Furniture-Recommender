"""
Track C owns this file.

REAL implementation: Google Places API (New) "Text Search", biased to the
user's location, returning the nearest furniture stores for a category.

- The API key is read from backend/.env (GOOGLE_PLACES_API_KEY). It is never
  written in code and .env is in .gitignore.
- Results are cached in memory per (category, lat, lng rounded to ~1 km), so
  repeated searches (changing the style dropdown, swapping items) cost no
  extra API calls. Places calls cost quota, so this matters.
- If the key is missing or Google fails (no internet, quota, API not enabled),
  the function returns a clearly-marked SAMPLE list instead of crashing, so
  the demo still runs. Sample entries have "source": "sample".

Return shape (docs/CONTRACTS.md section 4, extended):
  [{"name", "distance_km", "map_url", "address", "rating", "rating_count", "source"}]
"""

import json
import math
import os
import urllib.request
import urllib.error
from typing import List, Dict

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
SEARCH_RADIUS_M = 15000.0   # bias results to ~15 km around the user
MAX_RESULTS = 3
TIMEOUT_S = 8

# What to search for, per catalog category.
CATEGORY_QUERY = {
    "bed": "bed and mattress furniture store",
    "sofa": "sofa furniture store",
    "table": "dining table furniture store",
    "chair": "chair furniture store",
}

_cache: Dict[tuple, List[Dict]] = {}
_env_loaded = False
last_error = None  # last problem seen, shown in the backend terminal for debugging


def _load_env():
    """Tiny .env reader (avoids adding python-dotenv as a dependency)."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _sample_stores(category: str) -> List[Dict]:
    return [
        {"name": "Sample Store (add API key)", "distance_km": None, "address": "",
         "rating": None, "rating_count": None,
         "map_url": f"https://www.google.com/maps/search/{category}+furniture+store",
         "source": "sample"},
    ]


def _search_google(category: str, lat: float, lng: float, api_key: str) -> List[Dict]:
    body = {
        "textQuery": CATEGORY_QUERY.get(category, f"{category} furniture store"),
        "maxResultCount": 10,  # fetch a few, we sort by distance and keep the closest
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng},
                                    "radius": SEARCH_RADIUS_M}},
    }
    req = urllib.request.Request(
        SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": ("places.displayName,places.formattedAddress,places.location,"
                                 "places.rating,places.userRatingCount,places.googleMapsUri"),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.load(resp)

    stores = []
    for p in data.get("places", []):
        loc = p.get("location") or {}
        if "latitude" not in loc:
            continue
        stores.append({
            "name": (p.get("displayName") or {}).get("text", "Store"),
            "distance_km": round(_haversine_km(lat, lng, loc["latitude"], loc["longitude"]), 1),
            "address": p.get("formattedAddress", ""),
            "rating": p.get("rating"),
            "rating_count": p.get("userRatingCount"),
            "map_url": p.get("googleMapsUri")
                       or f"https://www.google.com/maps/search/?api=1&query={loc['latitude']},{loc['longitude']}",
            "source": "google",
        })
    stores.sort(key=lambda s: s["distance_km"])
    return stores[:MAX_RESULTS]


def find_stores(category: str, lat: float, lng: float) -> List[Dict]:
    """Nearest stores selling this furniture category, distance-ranked."""
    global last_error
    _load_env()
    key = (category, round(lat, 2), round(lng, 2))  # ~1 km cache cell
    if key in _cache:
        return _cache[key]

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        last_error = "GOOGLE_PLACES_API_KEY not found in backend/.env"
        print("[store_locator]", last_error)
        return _sample_stores(category)

    try:
        stores = _search_google(category, lat, lng, api_key)
        if not stores:
            return _sample_stores(category)  # not cached, so a later try can succeed
        _cache[key] = stores
        return stores
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        last_error = f"Google Places HTTP {e.code}: {detail}"
    except Exception as e:  # no internet, timeout, etc.
        last_error = f"Google Places call failed: {e}"
    print("[store_locator]", last_error)
    return _sample_stores(category)

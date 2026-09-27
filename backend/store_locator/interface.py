"""
Track C owns this file.

Contract: see docs/CONTRACTS.md section 4.

Real implementation: query the Google Places API (Nearby Search) filtered by
category keyword + user lat/lng, return distance-ranked results. Cache results
per (category, lat, lng) rounded to ~1km, per the store_locations table's
distance_cache/cached_at columns — Places API calls cost money/quota.
"""

from typing import List, Dict


def find_stores(category: str, lat: float, lng: float) -> List[Dict]:
    """
    MOCK IMPLEMENTATION — replace with real Google Places API integration.

    Args:
        category: recommended item category, e.g. "bed", "lighting".
        lat, lng: user's location.

    Returns:
        list matching docs/CONTRACTS.md section 4, distance-ranked.
    """
    return [
        {"name": "Urban Living Co.", "distance_km": 1.2, "map_url": "https://maps.google.com/?q=urban+living"},
        {"name": "Home Studio", "distance_km": 2.8, "map_url": "https://maps.google.com/?q=home+studio"},
    ]

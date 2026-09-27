# Inter-layer contracts

Read this before writing any layer's real logic. These are the shapes every
layer must produce/consume so the three tracks never block each other. If you
need to change a contract, message the other two tracks first — a silent
change breaks someone else's already-working code.

---

## 1. Perception layer (Track A) → everything downstream

**Function:** `backend/perception/interface.py :: analyze_room(image_path: str) -> dict`

```json
{
  "detections": [
    {"label": "sofa", "bbox": [x1, y1, x2, y2], "confidence": 0.91},
    {"label": "coffee_table", "bbox": [x1, y1, x2, y2], "confidence": 0.85}
  ],
  "empty_space": [
    {"region": "floor", "bbox": [x1, y1, x2, y2], "area_ratio": 0.22}
  ],
  "dominant_colors": ["#E8DCC8", "#4A4A4A", "#B08D57"],
  "style": {"label": "scandinavian", "confidence": 0.83},
  "needs_confirmation": false
}
```
`needs_confirmation: true` when `style.confidence` is below your chosen
threshold (synopsis suggests ~0.6) — the frontend should then prompt the user
to confirm/pick a style instead of auto-committing.

---

## 2. Product catalog (feeds Recommender) — from the dataset

Each catalog item, however sourced (HF dataset, scraped, manually curated),
should be normalized to:

```json
{
  "id": "itm_00123",
  "name": "Bauhaus Gold Bed",
  "category": "bed",
  "price": 24500,
  "style_tags": ["bauhaus"],
  "color_tags": ["gold"],
  "retailer_id": "ret_045",
  "image_url": "..."
}
```
`category` must be one of a fixed enum your team agrees on early
(e.g. seating, storage, lighting, decor, bed, table) — the Recommender picks
**one item per required category**, so the category taxonomy is a
cross-team decision, not just Track A/B's.

---

## 3. Recommender + Explainability (Track B) → API/frontend

**Function:** `backend/recommender/interface.py :: recommend(style, palette, budget, catalog) -> dict`

```json
{
  "selected_items": [
    {"item_id": "itm_00123", "category": "bed", "score": 0.88, "price": 24500}
  ],
  "total_price": 24500,
  "compatibility_score": 0.88,
  "method": "dp_optimal"
}
```

**Function:** `backend/explainability/interface.py :: explain(item, room_context) -> str`
Returns a single short human-readable sentence, e.g.
`"Selected for colour match with your room's beige palette and fits within your remaining budget."`

---

## 4. Store-locator (Track C) → frontend

**Function:** `backend/store_locator/interface.py :: find_stores(category: str, lat: float, lng: float) -> list`

```json
[
  {"name": "Urban Living Co.", "distance_km": 1.2, "map_url": "https://maps.google.com/..."}
]
```

---

## 5. Database schema (Track C owns `backend/db/models.py`)

Matches the synopsis's Database Design section exactly:
`users`, `room_photos`, `detections`, `style_palette`, `catalog_items`,
`recommendations`, `store_locations`. See `backend/db/models.py` — already
scaffolded, extend rather than redesign.

---

## Working agreement

- Every mock in this repo returns data in the **exact shape** above — don't
  build against the mock's specific fake values, build against its shape.
- If a contract needs to change, it's a one-line message to the other tracks
  before you do it, not after.

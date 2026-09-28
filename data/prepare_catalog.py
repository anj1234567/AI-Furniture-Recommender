"""
Run this ONCE, locally (needs internet), to turn the HF synthetic dataset
into the real catalog your recommender uses:

    cd data
    pip install datasets
    python prepare_catalog.py

Produces data/catalog.json in the exact shape docs/CONTRACTS.md section 2
requires, which backend/api/main.py loads automatically if present.

NOTE: this dataset only has 4 furniture "type" values (bed-heavy in the
preview, but 4 total across the full set) -- it's real product data, but it
doesn't cover every category your recommender's category taxonomy might
want (lighting, decor, storage, etc.). Extend with another source later if
you need broader category coverage; this gets you a genuinely real catalog
to demo with today.
"""

import json
import os
from collections import defaultdict
from datasets import load_dataset

# price_range is a category label in this dataset, not a number -- mapped to
# representative INR values so the DP/Greedy budget solvers have real prices
# to work with. Adjust these to whatever feels realistic for your report.
PRICE_MAP = {
    "budget": 2000,
    "standard": 5000,
    "premium": 9000,
    "custom": 12000,
    "elite": 15000,
    "luxury": 25000,
}

MAX_ITEMS_PER_TYPE = 150  # keeps the catalog + DP solver fast; raise if needed
IMAGE_DIR = "images"      # product photos are saved here as small JPEGs


def main():
    ds = load_dataset("filnow/furniture-synthetic-dataset", split="train")

    os.makedirs(IMAGE_DIR, exist_ok=True)
    per_type_count = defaultdict(int)
    catalog = []
    seen = set()

    for i, row in enumerate(ds):
        item_type = row["type"]
        if per_type_count[item_type] >= MAX_ITEMS_PER_TYPE:
            continue

        # Skip near-duplicate style+color+type combos for a bit more variety
        key = (item_type, row["style"], row["color"])
        if key in seen:
            continue
        seen.add(key)

        price = PRICE_MAP.get(row["price_range"], 5000)
        item_id = f"itm_{i:05d}"
        img = row["image"].convert("RGB")
        img.thumbnail((320, 320))
        img.save(os.path.join(IMAGE_DIR, f"{item_id}.jpg"), quality=80)
        catalog.append({
            "id": item_id,
            "image": f"/images/{item_id}.jpg",
            "name": f"{row['style'].title()} {row['color'].title()} {item_type.title()}",
            "category": item_type,
            "price": price,
            "style_tags": [row["style"]],
            "color_tags": [row["color"]],
            "material": row.get("material"),
            "room_type": row.get("room_type"),
        })
        per_type_count[item_type] += 1

    with open("catalog.json", "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"Wrote {len(catalog)} items to data/catalog.json")
    print("Items per category:", dict(per_type_count))


if __name__ == "__main__":
    main()

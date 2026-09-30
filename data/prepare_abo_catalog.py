"""
Builds the product catalog from the Amazon Berkeley Objects (ABO) dataset.
Unlike the old HuggingFace catalog, every item here has REAL dimensions,
a real colour (hex code) and a real product photo, so the app can check
whether a piece of furniture actually fits in the room.

Run ONCE on your laptop (needs internet):

    1. Download  https://amazon-berkeley-objects.s3.amazonaws.com/archives/abo-listings.tar
       and put it in  data/raw/abo-listings.tar   (about 83 MB, do NOT unzip it)
    2. cd data
       pip install pillow
       python prepare_abo_catalog.py

Result: data/catalog.json (your old catalog is copied to catalog_hf_backup.json)
and small product photos in data/images/.

Attribution (required by the ABO licence): product data, images and 3D
models are (c) Amazon.com, from the Amazon Berkeley Objects dataset
(Collins et al., CVPR 2022), licensed CC BY 4.0.

Honest note on prices: ABO has NO prices. Prices here are ESTIMATED from the
real size and material of each item (formula in estimate_price) and every
item is marked "price_source": "estimated". Say this in the review.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
from recommender.interface import _NAMED_COLORS, STYLE_GROUPS  # noqa: E402

S3 = "https://amazon-berkeley-objects.s3.amazonaws.com"
IMAGES_CSV_URL = f"{S3}/images/metadata/images.csv.gz"

# ABO product_type -> our catalog category.
CATEGORY_OF_TYPE = {
    "BED": "bed", "BED_FRAME": "bed",
    "SOFA": "sofa", "COUCH": "sofa",
    "CHAIR": "chair",
    "TABLE": "table",
}

# Plausible footprint side lengths in cm; anything outside is a data error
# (or a miniature / a set) and is dropped.
SIZE_LIMITS_CM = {
    "bed": (80, 260), "sofa": (100, 350), "chair": (30, 130), "table": (40, 300),
}

# Base price in INR for a median-size item, used by estimate_price.
BASE_PRICE = {"bed": 18000, "sofa": 22000, "chair": 6000, "table": 9000}
MATERIAL_FACTOR = {
    "leather": 1.5, "velvet": 1.2, "solid wood": 1.4, "wood": 1.15, "metal": 1.0,
    "steel": 1.0, "iron": 1.0, "rattan": 1.1, "glass": 1.1, "marble": 1.6,
    "fabric": 1.0, "linen": 1.05, "plastic": 0.7, "engineered wood": 0.85,
    "mdf": 0.8, "particle board": 0.75,
}

# Words in the product title -> style tag (tags belong to STYLE_GROUPS values).
STYLE_KEYWORDS = {
    "modern": "modern", "contemporary": "modern", "minimalist": "minimalist",
    "scandinavian": "scandinavian", "nordic": "nordic",
    "industrial": "industrial", "bohemian": "bohemian", "boho": "bohemian",
    "traditional": "traditional", "classic": "classic", "victorian": "victorian",
    "coastal": "coastal", "nautical": "coastal", "rustic": "rustic",
    "farmhouse": "rustic", "cabin": "rustic", "japanese": "japanese", "zen": "zen",
    "mid-century": "retro", "mid century": "retro", "retro": "retro",
    "vintage": "retro", "art deco": "deco", "eclectic": "eclectic",
}

# Words in the ABO category path -> the room types used by the recommender.
ROOM_KEYWORDS = [
    ("living room", "living"), ("bedroom", "bedroom"), ("kids", "kids"),
    ("nursery", "nursery"), ("kitchen", "dining"), ("dining", "dining"),
    ("home office", "office"), ("office", "office"),
    ("patio", "outdoor"), ("outdoor", "outdoor"),
]


# ---------------------------------------------------------------- helpers
def en_value(entries):
    """First en_* value of an ABO multilingual field, or None."""
    for e in entries or []:
        if str(e.get("language_tag", "")).lower().startswith("en"):
            return e.get("value")
    return None


def dim_cm(dims, key):
    d = (dims or {}).get(key) or {}
    nv = d.get("normalized_value") or {}
    val, unit = nv.get("value"), str(nv.get("unit", "")).lower()
    if val is None:
        return None
    if unit in ("inches", "inch"):
        return float(val) * 2.54
    if unit in ("centimeters", "centimetres", "cm"):
        return float(val)
    if unit in ("feet", "foot"):
        return float(val) * 30.48
    return None


def nearest_color_name(hex_code):
    h = hex_code.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    best, best_d = None, 1e18
    for name, (r2, g2, b2) in _NAMED_COLORS.items():
        d = (r - r2) ** 2 + (g - g2) ** 2 + (b - b2) ** 2
        if d < best_d:
            best, best_d = name, d
    return best


def glb_url(model_id):
    """Public URL of the product's 3D model (real-size glTF). The folder is the
    last character of the model id, as in ABO's own 3dmodels.csv."""
    if not model_id:
        return None
    return f"{S3}/3dmodels/original/{model_id[-1]}/{model_id}.glb"


def clean_name(name):
    for prefix in ("Amazon Brand - ", "Amazon Brand – ", "AmazonBasics ", "Amazon Basics "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()[:120]


def color_from_name(entries):
    """(name, hex) from ABO's colour text, or (None, None). Tries every en_*
    standardized value / raw value, longest match first ("dark brown" -> brown)."""
    texts = []
    for e in entries or []:
        if str(e.get("language_tag", "")).lower().startswith("en"):
            texts += [str(v) for v in e.get("standardized_values") or []] + [str(e.get("value", ""))]
    for t in texts:
        words = t.lower().replace("/", " ").replace("-", " ").split()
        for w in words:
            if w in _NAMED_COLORS:
                r, g, b = _NAMED_COLORS[w]
                return w, "#%02X%02X%02X" % (r, g, b)
    return None, None


# Things ABO files under BED/TABLE that are not what a shopper means.
BED_JUNK = ("drawer", "storage box", "underbed", "under bed", "organiser", "organizer", "trundle only",
            "slat", "base only", "bed rail", "bedside", "cot ", "crib", "bassinet", "mattress")
TABLE_JUNK = ("bedside", "nightstand", "night stand", "tv stand", "tray", "runner", "cloth", "lamp")
MIN_BED_CM = (170, 80)   # a real bed is at least 170 x 80 cm

PET_WORDS = ("pet", "dog", "cat ", "cats", "puppy", "kitten", "cuddler", "cave bed")


def style_tags_from(name, style_field):
    text = f"{name or ''} {style_field or ''}".lower()
    tags = []
    for word, tag in STYLE_KEYWORDS.items():
        if word in text and tag not in tags:
            tags.append(tag)
    return tags


def room_type_from(nodes):
    text = " ".join(
        str(n.get("node_name") or n.get("path") or "") for n in (nodes or [])
    ).lower()
    for word, room in ROOM_KEYWORDS:
        if word in text:
            return room
    return None


def estimate_price(category, footprint_cm2, median_cm2, material):
    size_factor = (footprint_cm2 / median_cm2) ** 0.6 if median_cm2 else 1.0
    size_factor = min(max(size_factor, 0.5), 2.5)
    mat = (material or "").lower()
    mat_factor = next((f for k, f in MATERIAL_FACTOR.items() if k in mat), 1.0)
    return int(round(BASE_PRICE[category] * size_factor * mat_factor / 500.0) * 500)


BED_EXCLUDE = ("headboard", "mattress", "bed rail", "skirt", "sheet", "pillow", "topper",
               "canopy", "curtain", "blanket", "comforter", "frame only for", "replacement")


def category_from_nodes(nodes, name):
    """Beds and some sofas are filed under generic product types in ABO
    (HOME, HOME_BED_AND_BATH, ...), so also look at the category path."""
    paths = [str(n.get("node_name") or n.get("path") or "").lower() for n in (nodes or [])]
    low_name = (name or "").lower()
    for p in paths:
        if p.rstrip("/").endswith(("/beds", "/bed frames", "/beds, frames & bases", "/platform beds",
                                   "/daybeds", "/bunk beds", "/loft beds")) \
                or "/beds/" in p or "/bed frames" in p:
            if not any(w in low_name for w in BED_EXCLUDE) and "bed" in low_name:
                return "bed"
        if p.rstrip("/").endswith(("/sofas & couches", "/loveseats")):
            return "sofa"
    return None


def parse_listing(row):
    """One ABO listing -> catalog dict (without price/image), or None."""
    name = en_value(row.get("item_name"))
    ptypes = [str(p.get("value", "")).upper() for p in row.get("product_type") or []]
    category = next((CATEGORY_OF_TYPE[p] for p in ptypes if p in CATEGORY_OF_TYPE), None)
    if category is None:
        category = category_from_nodes(row.get("node"), name)
    if not name or not category or not row.get("main_image_id"):
        return None
    paths = " ".join(str(n.get("node_name") or n.get("path") or "") for n in row.get("node") or []).lower()
    low = name.lower()
    if "/dogs" in paths or "/cats" in paths or "pet supplies" in paths or any(w in low for w in PET_WORDS):
        return None

    dims = row.get("item_dimensions") or {}
    w, l, h = dim_cm(dims, "width"), dim_cm(dims, "length"), dim_cm(dims, "height")
    if not w or not l:
        return None
    if category == "bed" and (any(w in low for w in BED_JUNK)
                              or max(w, l) < MIN_BED_CM[0] or min(w, l) < MIN_BED_CM[1]):
        return None
    if category == "table" and any(w in low for w in TABLE_JUNK):
        return None
    lo, hi = SIZE_LIMITS_CM[category]
    if not (lo <= max(w, l) <= hi) or min(w, l) < lo * 0.3:
        return None

    # Colour: use the hex code if ABO has one; otherwise fall back to the
    # colour NAME (e.g. "Walnut") looked up in our named-colour table.
    codes = row.get("color_code") or []
    color_name, color_hex = None, None
    if codes and str(codes[0]).startswith("#") and len(str(codes[0])) == 7:
        color_hex = str(codes[0]).upper()
        color_name = nearest_color_name(color_hex)
    else:
        color_name, color_hex = color_from_name(row.get("color"))
    if color_name is None:
        return None

    material = en_value(row.get("material"))
    return {
        "abo_id": row["item_id"],
        "main_image_id": row["main_image_id"],
        "name": clean_name(name),
        "category": category,
        "style_tags": style_tags_from(name, en_value(row.get("style"))),
        "color_tags": [color_name],
        "color_hex": color_hex,
        "material": material.strip().lower()[:40] if material else None,
        "room_type": room_type_from(row.get("node")),
        "width_cm": round(max(w, l)),   # long side
        "depth_cm": round(min(w, l)),   # short side
        "height_cm": round(h) if h else None,
        "has_3d_model": bool(row.get("3dmodel_id")),
        "glb_url": glb_url(row.get("3dmodel_id")),
    }


def read_listings(tar_path):
    """Stream every listing out of abo-listings.tar without unpacking it."""
    with tarfile.open(tar_path) as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".json.gz"):
                continue
            with gzip.open(tar.extractfile(member), "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue


def load_image_paths(cache_path):
    if not os.path.exists(cache_path):
        print("Downloading image index (about 20 MB)...")
        urllib.request.urlretrieve(IMAGES_CSV_URL, cache_path)
    paths = {}
    with gzip.open(cache_path, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            paths[row["image_id"]] = row["path"]
    return paths


def download_image(item_id, rel_path, out_dir):
    dest = os.path.join(out_dir, f"{item_id}.jpg")
    if os.path.exists(dest):
        return True
    try:
        from PIL import Image
        with urllib.request.urlopen(f"{S3}/images/small/{rel_path}", timeout=30) as r:
            img = Image.open(io.BytesIO(r.read())).convert("RGB")
        img.thumbnail((320, 320))
        img.save(dest, quality=82)
        return True
    except Exception:
        return False


def pick(cands, n):
    """Deterministic pick: items with a 3D model first, then a stable shuffle,
    while limiting near-duplicate (same name start) listings."""
    def key(c):
        return (not c["has_3d_model"], hashlib.md5(c["abo_id"].encode()).hexdigest())
    chosen, seen_names = [], {}
    for c in sorted(cands, key=key):
        stem = " ".join(c["name"].lower().split()[:4])
        if seen_names.get(stem, 0) >= 8:
            continue
        seen_names[stem] = seen_names.get(stem, 0) + 1
        chosen.append(c)
        if len(chosen) >= n:
            break
    return chosen


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", default=os.path.join(HERE, "raw", "abo-listings.tar"))
    ap.add_argument("--per-category", type=int, default=200)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    if not os.path.exists(args.tar):
        sys.exit(f"Cannot find {args.tar}\nDownload abo-listings.tar and put it there (see top of this file).")
    os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
    out_dir = os.path.join(HERE, "images")
    os.makedirs(out_dir, exist_ok=True)

    print("Reading listings...")
    total, product_types, by_cat = 0, {}, {}
    for row in read_listings(args.tar):
        total += 1
        for p in row.get("product_type") or []:
            v = str(p.get("value", "")).upper()
            product_types[v] = product_types.get(v, 0) + 1
        item = parse_listing(row)
        if item:
            by_cat.setdefault(item["category"], []).append(item)
    print(f"Read {total} listings. Usable per category:",
          {k: len(v) for k, v in by_cat.items()})
    top = sorted(product_types.items(), key=lambda kv: -kv[1])[:25]
    print("Most common product types in ABO (for adding categories later):", top)

    img_paths = load_image_paths(os.path.join(HERE, "raw", "images.csv.gz"))

    chosen = []
    for cat, cands in by_cat.items():
        cands = [c for c in cands if c["main_image_id"] in img_paths]
        chosen += pick(cands, args.per_category)

    print(f"Downloading {len(chosen)} product photos...")
    with ThreadPoolExecutor(args.workers) as ex:
        ok = list(ex.map(
            lambda c: download_image(f"abo_{c['abo_id']}", img_paths[c["main_image_id"]], out_dir),
            chosen))
    chosen = [c for c, good in zip(chosen, ok) if good]

    # Price estimate needs the median footprint of each category.
    med = {}
    for cat in {c["category"] for c in chosen}:
        areas = sorted(c["width_cm"] * c["depth_cm"] for c in chosen if c["category"] == cat)
        med[cat] = areas[len(areas) // 2]

    catalog = []
    for c in chosen:
        catalog.append({
            "id": f"abo_{c['abo_id']}",
            "image": f"/images/abo_{c['abo_id']}.jpg",
            "name": c["name"],
            "category": c["category"],
            "price": estimate_price(c["category"], c["width_cm"] * c["depth_cm"],
                                    med[c["category"]], c["material"]),
            "price_source": "estimated",
            "style_tags": c["style_tags"],
            "color_tags": c["color_tags"],
            "color_hex": c["color_hex"],
            "material": c["material"],
            "room_type": c["room_type"],
            "width_cm": c["width_cm"],
            "depth_cm": c["depth_cm"],
            "height_cm": c["height_cm"],
            "has_3d_model": c["has_3d_model"],
            "glb_url": c["glb_url"],
            "source": "Amazon Berkeley Objects (CC BY 4.0), (c) Amazon.com",
        })

    old = os.path.join(HERE, "catalog.json")
    if os.path.exists(old):
        shutil.copy(old, os.path.join(HERE, "catalog_hf_backup.json"))
    with open(old, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=1)

    counts = {}
    for c in catalog:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    tagged = sum(1 for c in catalog if c["style_tags"])
    print(f"Wrote {len(catalog)} items to data/catalog.json: {counts}")
    print(f"{tagged} items have a style tag; {sum(c['has_3d_model'] for c in catalog)} have a 3D model.")


if __name__ == "__main__":
    main()

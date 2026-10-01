"""
Track C owns this file.

This wires all four layers together behind one API. Perception and the
catalog are real (see backend/perception/interface.py and
data/prepare_catalog.py); explainability and store-locator are still
mocked. As each remaining piece lands, this file doesn't need to change
(that's the point of the contracts).
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
load_dotenv()


import shutil
import os
import re
import json
import urllib.request

from perception.interface import analyze_room
from perception.preprocess import REJECT_FLAT_RATIO
from recommender.interface import (
    recommend, find_missing_categories, filter_to_missing, filter_to_room, MIN_DETECTION_CONFIDENCE,
    unmapped_colors, classify_detection, STYLE_OPTIONS, ROOM_OPTIONS, _no_choice,
    space_summary, footprint_m2,
)
from explainability.interface import explain
from recommender.interface import DETECTION_TO_CATEGORY
from recommender.quality import clean_catalog
from store_locator.interface import find_stores
from db import init_db
from space.scene import analyze_scene

from catalog_module.interface import search_online, pick_best, build_query, detect_color

app = FastAPI(title="AI Furniture Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Product photos saved by data/prepare_catalog.py, served at /images/<id>.jpg
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.on_event("startup")
def on_startup():
    init_db()


# Real catalog (see data/prepare_catalog.py) if it's been generated, else
# fall back to the small mock so the app still runs without it.
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalog.json")
try:
    with open(CATALOG_PATH) as f:
        CATALOG = json.load(f)
    CATALOG, _dropped = clean_catalog(CATALOG)
    print(f"Loaded real catalog: {len(CATALOG)} items ({_dropped} removed: folding tables, TV units, office chairs, bad sizes...)")
except FileNotFoundError:
    print("data/catalog.json not found -- using small mock catalog. "
          "Run data/prepare_catalog.py to generate the real one.")
    CATALOG = [
        {"id": "itm_00123", "name": "Bauhaus Gold Bed", "category": "bed",
         "price": 24500, "style_tags": ["bauhaus"], "color_tags": ["gold"], "retailer_id": "ret_045"},
        {"id": "itm_00456", "name": "Scandinavian Floor Lamp", "category": "lighting",
         "price": 3200, "style_tags": ["scandinavian"], "color_tags": ["beige"], "retailer_id": "ret_012"},
    ]


_unmapped = unmapped_colors(CATALOG)
if _unmapped:
    print("Colour names not in the colour table (scored as neutral):", _unmapped)


@app.post("/analyze")
async def analyze(
    photo: UploadFile = File(...),
    budget: float = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    style: str = Form(""),      # optional: style picked by the user
    room_type: str = Form(""),  # optional: room type picked by the user
    room_width_m: float = Form(0),   # optional: room size in metres (0 = not given)
    room_length_m: float = Form(0),
):
    """Full pipeline: upload -> perception -> recommend -> explain -> stores."""
    photo_path = os.path.join(UPLOAD_DIR, photo.filename)
    with open(photo_path, "wb") as f:
        shutil.copyfileobj(photo.file, f)

    perception_result = analyze_room(photo_path)

    if perception_result["image_quality"]["flat_ratio"] > REJECT_FLAT_RATIO:
        raise HTTPException(
            status_code=400,
            detail="This doesn't look like a room photo (it looks like a screenshot or graphic). "
                   "Please upload a photo of a room.",
        )

    # Decide which detections count as "the room already has this".
    for d in perception_result["detections"]:
        d["counted"], d["not_counted_reason"] = classify_detection(d)

    # Gap analysis: only recommend categories the room is missing.
    # missing = find_missing_categories(CATALOG, perception_result["detections"])
    # candidate_catalog = filter_to_missing(CATALOG, missing)
    # if str(room_type).strip().lower() != "outdoor":   # no patio furniture for an indoor room
    #     candidate_catalog = [i for i in candidate_catalog if i.get("room_type") != "outdoor"] or candidate_catalog
    # upgrade_mode = len(missing) == 0  # room already has every catalog category
    
    # Normalize selected room
    room_type = None if _no_choice(room_type) else str(room_type).strip().lower()

# First restrict the catalog to furniture relevant to this room.
    room_catalog = filter_to_room(CATALOG, room_type)

# Find only the furniture categories missing from this room.
    missing = find_missing_categories(
    room_catalog,
    perception_result["detections"]
)

# Recommend only the missing furniture categories.
    candidate_catalog = filter_to_missing(
    room_catalog,
    missing
)

    upgrade_mode = len(missing) == 0

    # Style: the user's pick wins. Until the style classifier is trained,
    # the perception layer returns "unclassified", so this pick is the
    # source of the style (docs/CONTRACTS.md: user confirmation flow).
    if not _no_choice(style):
        style_source = "user"
    else:
        style, style_source = perception_result["style"]["label"], "model"
    room_type = None if _no_choice(room_type) else room_type
    palette = perception_result["dominant_colors"]

    # Floor space: from the size the user typed, otherwise estimated from the photo
    # (depth model). If neither works, the floor-space check is skipped.
    space, room_dims, space_m2, space_source = None, None, None, None
    scene = analyze_scene(photo_path)          # one depth pass: room size, floor plane, ceiling
    if room_width_m > 0 and room_length_m > 0:
        space_source = "user"
    elif scene["room"]:
        room_width_m, room_length_m, space_source = scene["room"]["width_m"], scene["room"]["length_m"], "estimated"
    if space_source:
        present = {DETECTION_TO_CATEGORY[d["label"]] for d in perception_result["detections"]
                   if d.get("counted") and d["label"] in DETECTION_TO_CATEGORY}
        space = space_summary(room_width_m, room_length_m, CATALOG, present)
        space["source"] = space_source
        room_dims, space_m2 = (room_width_m, room_length_m), space["usable_m2"]

    rec_result = recommend(style=style, palette=palette, budget=budget,
                           catalog=candidate_catalog, method="dp_optimal", room_type=room_type,
                           room_dims_m=room_dims, space_m2=space_m2)
    greedy_result = recommend(style=style, palette=palette, budget=budget,
                              catalog=candidate_catalog, method="greedy", room_type=room_type,
                              room_dims_m=room_dims, space_m2=space_m2)

    room_context = {
        "style": style,
        "dominant_colors": palette,
        "budget": budget,
        "missing_categories": missing,
        "room_type": room_type,
        "space": space,
    }
    catalog_by_id = {item["id"]: item for item in CATALOG}

    def decorate(entry):
        """Add name, picture, material and explanation from the catalog."""
        full = {**catalog_by_id.get(entry["item_id"], {}), **entry}
        entry["name"] = full.get("name", entry["category"])
        entry["image"] = full.get("image")
        entry["glb_url"] = full.get("glb_url")
        entry["model_url"] = f"/model/{entry['item_id']}" if full.get("glb_url") else None
        entry["color_hex"] = full.get("color_hex")
        entry["material"] = full.get("material")
        entry["item_room_type"] = full.get("room_type")
        entry["style_tags"] = full.get("style_tags", [])
        entry["color_tags"] = full.get("color_tags", [])
        entry["explanation"] = explain(full, room_context)

    for item in rec_result["selected_items"]:
        decorate(item)
        item["nearby_stores"] = find_stores(item["category"], lat, lng)
    for alts in rec_result["alternatives"].values():
        for alt in alts:
            decorate(alt)

    used = rec_result["total_price"]
    return {
        "perception": perception_result,
        "scene": scene["camera"],     # camera + floor plane for the 3D-in-photo view
        "style_used": {"label": style, "source": style_source},
        "room_type_used": room_type,
        "space": None if space is None else {
            **space, "used_m2": round(sum(footprint_m2(catalog_by_id[i["item_id"]]) for i in rec_result["selected_items"]), 2)},
        "budget_summary": {
            "budget": budget,
            "used": used,
            "left": budget - used,
            "percent_used": round(100 * used / budget) if budget > 0 else 0,
        },
        "recommendation": rec_result,
        "gap_analysis": {
            "missing_categories": missing,
            "upgrade_mode": upgrade_mode,
            "min_confidence": MIN_DETECTION_CONFIDENCE,
        },
        "comparison": {
            "dp_optimal": {
                "total_price": rec_result["total_price"],
                "total_score": round(sum(i["score"] for i in rec_result["selected_items"]), 3),
                "items": len(rec_result["selected_items"]),
            },
            "greedy": {
                "total_price": greedy_result["total_price"],
                "total_score": round(sum(i["score"] for i in greedy_result["selected_items"]), 3),
                "items": len(greedy_result["selected_items"]),
            },
        },
    }


# 3D models live on Amazon's server, which the browser may not be allowed to read
# directly (CORS). This endpoint downloads a model once, keeps it in data/models/,
# and serves it to the page from here.
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "models")
os.makedirs(MODELS_DIR, exist_ok=True)
_BY_ID = {i["id"]: i for i in CATALOG}


@app.get("/model/{item_id}")
def model_file(item_id: str):
    item = _BY_ID.get(item_id)
    if not item or not item.get("glb_url"):
        raise HTTPException(status_code=404, detail="No 3D model for this item.")
    path = os.path.join(MODELS_DIR, re.sub(r"[^A-Za-z0-9_-]", "", item_id) + ".glb")
    if not os.path.exists(path):
        tmp = path + ".part"
        try:
            urllib.request.urlretrieve(item["glb_url"], tmp)
            os.replace(tmp, path)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not download the 3D model: {exc}")
    return FileResponse(path, media_type="model/gltf-binary")


@app.get("/options")
def options():
    """Style and room-type choices for the frontend dropdowns."""
    return {"styles": STYLE_OPTIONS, "room_types": ROOM_OPTIONS}

# @app.get("/online/search")
# def online_search(
#     q: str = Query(..., max_length=80),
#     category: str = Query(..., max_length=30),
#     max_price: float | None = None,
#     ref_price: float | None = None,
#     limit: int = Query(4, ge=1, le=10),
# ):
#     try:
#         items = search_online(q, category)
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"Online search failed: {e}")
#     if max_price is not None:
#         items = [i for i in items if i["price"] is not None and i["price"] <= max_price]
#     return {"items": pick_best(items, category, ref_price, limit)}

@app.get("/online/search")
def online_search(
    category: str = Query(..., max_length=30),
    ref_name: str = Query("", max_length=200),
    ref_color: str = Query("", max_length=30),
    room_type: str = Query("", max_length=40),
    max_price: float | None = None,
    ref_price: float | None = None,
    limit: int = Query(4, ge=1, le=10),
):
    q = build_query(ref_name, category, ref_color)
    try:
        items = search_online(q, category)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Online search failed: {e}")
    if max_price is not None:
        items = [i for i in items if i["price"] is not None and i["price"] <= max_price]
    color = detect_color(ref_name, ref_color)
    return {"query": q, "items": pick_best(items, category, ref_price, ref_name, color, room_type, limit)}

@app.get("/health")
def health():
    return {"status": "ok"}

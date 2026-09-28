"""
Track C owns this file.

This wires all four layers together behind one API. Perception and the
catalog are real (see backend/perception/interface.py and
data/prepare_catalog.py); explainability and store-locator are still
mocked. As each remaining piece lands, this file doesn't need to change
(that's the point of the contracts).
"""

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import json

from perception.interface import analyze_room
from recommender.interface import (
    recommend, find_missing_categories, filter_to_missing, MIN_DETECTION_CONFIDENCE,
)
from explainability.interface import explain
from store_locator.interface import find_stores
from db import init_db

app = FastAPI(title="AI Furniture Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()


# Real catalog (see data/prepare_catalog.py) if it's been generated, else
# fall back to the small mock so the app still runs without it.
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "catalog.json")
try:
    with open(CATALOG_PATH) as f:
        CATALOG = json.load(f)
    print(f"Loaded real catalog: {len(CATALOG)} items")
except FileNotFoundError:
    print("data/catalog.json not found -- using small mock catalog. "
          "Run data/prepare_catalog.py to generate the real one.")
    CATALOG = [
        {"id": "itm_00123", "name": "Bauhaus Gold Bed", "category": "bed",
         "price": 24500, "style_tags": ["bauhaus"], "color_tags": ["gold"], "retailer_id": "ret_045"},
        {"id": "itm_00456", "name": "Scandinavian Floor Lamp", "category": "lighting",
         "price": 3200, "style_tags": ["scandinavian"], "color_tags": ["beige"], "retailer_id": "ret_012"},
    ]


@app.post("/analyze")
async def analyze(
    photo: UploadFile = File(...),
    budget: float = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
):
    """Full pipeline: upload -> perception -> recommend -> explain -> stores."""
    photo_path = os.path.join(UPLOAD_DIR, photo.filename)
    with open(photo_path, "wb") as f:
        shutil.copyfileobj(photo.file, f)

    perception_result = analyze_room(photo_path)

    # Gap analysis: only recommend categories the room is missing.
    missing = find_missing_categories(CATALOG, perception_result["detections"])
    candidate_catalog = filter_to_missing(CATALOG, missing)
    upgrade_mode = len(missing) == 0  # room already has every catalog category

    style = perception_result["style"]["label"]
    palette = perception_result["dominant_colors"]

    rec_result = recommend(style=style, palette=palette, budget=budget,
                           catalog=candidate_catalog, method="dp_optimal")
    greedy_result = recommend(style=style, palette=palette, budget=budget,
                              catalog=candidate_catalog, method="greedy")

    room_context = {
        "style": style,
        "dominant_colors": palette,
        "budget": budget,
        "missing_categories": missing,
    }
    catalog_by_id = {item["id"]: item for item in CATALOG}
    for item in rec_result["selected_items"]:
        full = {**catalog_by_id.get(item["item_id"], {}), **item}
        item["name"] = full.get("name", item["category"])
        item["explanation"] = explain(full, room_context)
        item["nearby_stores"] = find_stores(item["category"], lat, lng)

    return {
        "perception": perception_result,
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


@app.get("/health")
def health():
    return {"status": "ok"}

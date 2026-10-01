"""
Track C owns this file.

This wires all four layers together behind one API. Perception and the
catalog are real (see backend/perception/interface.py and
data/prepare_catalog.py); explainability and store-locator are still
mocked. As each remaining piece lands, this file doesn't need to change
(that's the point of the contracts).
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import shutil
import os
import re
import json
import urllib.request
import time

import cv2
import numpy as np

from perception.interface import analyze_room
from perception.preprocess import REJECT_FLAT_RATIO
from recommender.interface import (
    recommend, find_missing_categories, filter_to_missing, MIN_DETECTION_CONFIDENCE,
    unmapped_colors, classify_detection, STYLE_OPTIONS, ROOM_OPTIONS, _no_choice,
    space_summary, footprint_m2,
)
from explainability.interface import explain
from recommender.interface import DETECTION_TO_CATEGORY
from recommender.quality import clean_catalog
from recommender.room_fit import (
    ROOM_CATEGORIES, room_kind, infer_room_kind, fit_catalog_to_room, plausible_room,
)
from perception.style_zeroshot import classify_room
from recommender.style_filter import filter_by_style
from recommender.detections_fit import drop_duplicates, recount

MIN_DISPLAY_CONFIDENCE = 0.30   # detections below this are not shown at all
from store_locator.interface import find_stores
from db import init_db
from space.scene import analyze_scene
from editing.inpaint import boxes_to_mask, remove_objects, grow_mask

app = FastAPI(title="AI Furniture Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server default
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Inpaint-Method"],
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


print("Style: chosen by the user only (no automatic style detection).")


def _style_choices():
    """STYLE_OPTIONS can be plain strings or {value, label} objects -> [(value, label)]."""
    out = []
    for o in STYLE_OPTIONS or []:
        if isinstance(o, str):
            v, l = o, o
        elif isinstance(o, dict):
            v = o.get("value") or o.get("id") or o.get("key") or o.get("label") or ""
            l = o.get("label") or o.get("name") or v
        elif isinstance(o, (list, tuple)) and o:
            v, l = o[0], (o[1] if len(o) > 1 else o[0])
        else:
            continue
        if str(v).strip() and not _no_choice(str(v)) and not _no_choice(str(l)):
            out.append((str(v), str(l)))
    return out


STYLE_CHOICES = _style_choices()


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
    perception_result["detections"] = drop_duplicates(perception_result["detections"])   # one object, one box
    for d in perception_result["detections"]:
        d["counted"], d["not_counted_reason"] = classify_detection(d)
    _img = cv2.imread(photo_path)
    if _img is not None:     # clearly visible furniture must count even at 45-60% confidence
        recount(perception_result["detections"], DETECTION_TO_CATEGORY, _img.shape[1], _img.shape[0])

    # Gap analysis: only recommend categories the room is missing AND that belong in this room
    # (no sofa for a kitchen, no bed for a living room).
    kind = room_kind(room_type)
    kind_source = "user" if kind else None
    if kind is None:
        kind = infer_room_kind(perception_result["detections"], DETECTION_TO_CATEGORY)
        kind_source = "photo" if kind else None
    if kind is None:           # the furniture did not settle it: ask CLIP what kind of room the photo shows
        rc = classify_room(photo_path)
        if rc and rc["confidence"] >= 0.40:
            kind, kind_source = rc["kind"], "photo"
    allowed = ROOM_CATEGORIES.get(kind)
    # What the room already has = the detections that count for the gap analysis (decided above).
    present_cats = {DETECTION_TO_CATEGORY[d["label"]] for d in perception_result["detections"]
                    if d.get("counted") and d["label"] in DETECTION_TO_CATEGORY}
    _seen = []
    for i in CATALOG:
        c = i.get("category")
        if c is not None and c not in _seen:
            _seen.append(c)
    missing_all = [c for c in _seen if c not in present_cats]
    if allowed:
        missing = [c for c in missing_all if str(c).lower() in allowed]
        upgrade_mode = not missing           # room already has everything it needs: suggest upgrades
        cats = {str(c).lower() for c in missing} if missing else set(allowed)
        candidate_catalog = [i for i in CATALOG if str(i.get("category", "")).lower() in cats]
    else:
        missing = missing_all
        candidate_catalog = filter_to_missing(CATALOG, missing)
        upgrade_mode = len(missing) == 0     # room already has every catalog category
    if str(room_type).strip().lower() != "outdoor" and kind != "outdoor":   # no patio furniture for an indoor room
        candidate_catalog = [i for i in candidate_catalog if i.get("room_type") != "outdoor"] or candidate_catalog
    candidate_catalog = fit_catalog_to_room(candidate_catalog, kind)   # bedside table for a bedroom, dining table for a kitchen

    # Style: only what the user picked. "Not sure" = no style preference (neutral scoring, no filter).
    if not _no_choice(style):
        style_source = "user"
        perception_result["style"] = {"label": style, "confidence": 1.0, "source": "user"}
    else:
        style, style_source = "unclassified", "none"
        perception_result["style"] = {"label": "unclassified", "confidence": 0.0, "source": "none"}
    perception_result["needs_confirmation"] = False
    # Only furniture in the chosen style is suggested (swap alternatives come from the same list).
    candidate_catalog, style_filter_info = filter_by_style(candidate_catalog, style)
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
        # one photo shows only part of a room, so keep the estimate inside a normal range for this room
        room_width_m, room_length_m, _ = plausible_room(room_width_m, room_length_m, kind)
    if space_source:
        space = space_summary(room_width_m, room_length_m, CATALOG, present_cats)
        space["source"] = space_source
        space["room_w_m"], space["room_l_m"] = round(float(room_width_m), 1), round(float(room_length_m), 1)   # exactly the size used everywhere
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

    # Detections list for the page: just what was found and how sure the model is. Whether a detection
    # also counts for the gap analysis was decided above; the page does not need to explain that.
    shown = []
    for d in perception_result["detections"]:
        if float(d.get("confidence", 0)) < MIN_DISPLAY_CONFIDENCE:
            continue
        d["counts_for_gap"] = bool(d.get("counted"))
        d["counted"], d["not_counted_reason"] = True, None
        shown.append(d)
    perception_result["detections"] = shown

    used = rec_result["total_price"]
    return {
        "perception": perception_result,
        "scene": scene["camera"],     # camera + floor plane for the 3D-in-photo view
        "mesh": None,                 # the orbit "Room in 3D" view was removed; keeps the response small
        "style_used": {"label": style, "source": style_source, "ranking": None,
                       "confidence": perception_result["style"].get("confidence")},
        "room_type_used": room_type,
        "room_kind": {"kind": kind, "source": kind_source},
        "style_model_loaded": True,      # style is chosen by the user, so no model is needed
        "style_filter": style_filter_info,
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
            "present_categories": sorted(str(c) for c in present_cats),
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


@app.post("/inpaint")
def inpaint(
    photo: UploadFile = File(...),
    boxes: str = Form("[]"),          # JSON [[x1,y1,x2,y2], ...] in photo pixels (detected objects to remove)
    mask: UploadFile = File(None),    # optional PNG the user painted (white = remove)
):
    """Remove objects from the photo. Returns the cleaned JPEG; the page then re-analyses it."""
    path = os.path.join(UPLOAD_DIR, f"inpaint_src_{int(time.time() * 1000)}.jpg")
    with open(path, "wb") as f:
        shutil.copyfileobj(photo.file, f)
    bgr = cv2.imread(path)
    if bgr is None:
        raise HTTPException(status_code=400, detail="Could not read the photo.")
    try:
        box_list = json.loads(boxes or "[]")
    except ValueError:
        raise HTTPException(status_code=400, detail="boxes must be JSON.")
    m = boxes_to_mask(bgr.shape, box_list, bgr=bgr, refine=True) if box_list else np.zeros(bgr.shape[:2], np.uint8)
    if mask is not None:
        painted = cv2.imdecode(np.frombuffer(mask.file.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
        if painted is not None:
            painted = cv2.resize(painted, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
            m = np.maximum(m, grow_mask(painted, 0.012))
    if not m.any():
        raise HTTPException(status_code=400, detail="Nothing selected. Click a detected object or paint over it.")
    if m.mean() / 255.0 > 0.6:
        raise HTTPException(status_code=400, detail="That would remove most of the photo. Select smaller areas.")
    cleaned, engine = remove_objects(bgr, m)
    ok, buf = cv2.imencode(".jpg", cleaned, [cv2.IMWRITE_JPEG_QUALITY, 96])
    if not ok:
        raise HTTPException(status_code=500, detail="Could not encode the cleaned photo.")
    return Response(content=buf.tobytes(), media_type="image/jpeg", headers={"X-Inpaint-Method": engine})


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


@app.get("/health")
def health():
    return {"status": "ok"}

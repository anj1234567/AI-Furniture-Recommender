# Implementation roadmap

## Phase 0 — This week (all 3, together)
- Agree on the category taxonomy (seating, storage, lighting, decor, bed, table, ...)
- Agree on style label set (start small — Modern, Minimalist, Scandinavian,
  Traditional, Bohemian — extend later, your synopsis explicitly designs for this)
- Push this scaffold to GitHub, each person clones it, confirms `uvicorn` runs
  and returns mock data end-to-end
- Track C stands up the DB (SQLite is fine for dev) from `backend/db/models.py`

## Phase 1 — Build against mocks (parallel, ~2-3 weeks)
- **A**: source/collect room-scene datasets (COCO indoor-furniture subset,
  HomeObjects-3K — named in your synopsis), fine-tune YOLOv8 for detection,
  build K-means colour extraction, fine-tune MobileNetV3 style classifier
- **B**: normalize the HF synthetic dataset into the catalog_items shape,
  implement the MCKP DP solver, implement the Greedy baseline, implement
  rule-based (or LLM-templated) explanations
- **C**: build real FastAPI routes, wire the DB, integrate Google Places API,
  build the React upload/budget/results flow — all against the mocks

## Phase 2 — Integration (all 3, ~1 week)
- Swap each mock for its real implementation one at a time, re-test the full
  flow after each swap
- End-to-end test: upload photo → budget → recommended set with explanations
  → nearby stores

## Phase 3 — Evaluation (per your synopsis's objectives)
- Evaluate DP-optimal MCKP vs Greedy vs independent top-k, on style-coherence
  and budget-adherence, over a curated set of room photos
- Write up the Scalability Analysis Report section

## Phase 4 — Polish
- Confidence thresholds + "needs manual review" flow for low-confidence style/colour
- Input validation, file-type/size checks on upload (safety section of your synopsis)
- Basic auth if in scope, HTTPS/rate-limiting notes for the report even if not
  fully implemented in the student build

## Immediately after this
Tell me which review (Review 1 / Review 2) is coming up first and what your
guide expects to see, and I'll help prioritize which of the above to have
working demo-ready by that date.

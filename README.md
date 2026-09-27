# AI-Powered Interior Design & Furniture Recommendation Platform

FF No. 180 — Group 36. Shrey Rawal, Tanvi Rawal, Anjali Bhau.

A user uploads a room photo + total budget. The system detects existing furniture
and empty space, extracts colour palette and style, then recommends a
budget-constrained, style-coherent set of furniture (solved as a Multi-Choice
Knapsack Problem via Dynamic Programming vs a Greedy baseline), explains each
pick, and links categories to nearby physical stores.

## Team split (by layer — work in parallel, no one blocks on anyone else)

| Track | Owner | Folder |
|---|---|---|
| A — Perception (detection, colour, style) | TBD | `backend/perception/` |
| B — Recommendation + Explainability (MCKP/DP, Greedy, explanations) | TBD | `backend/recommender/`, `backend/explainability/` |
| C — Store-locator + Application (API, DB, frontend) | TBD | `backend/store_locator/`, `backend/api/`, `backend/db/`, `frontend/` |

**Fill in the owners above and edit the branch names below to match GitHub usernames.**

## How parallel dev works here

Every layer talks to the others only through the JSON contracts defined in
[`docs/CONTRACTS.md`](docs/CONTRACTS.md). Each module currently ships with a
**mock implementation** that returns realistic fake data matching its contract.
That means:

- Track A can build the real detector while Tracks B and C keep using the mock
  perception output and never get blocked.
- Track B can build the real MCKP solver while Track C wires up the API using
  the mock recommender output.
- Track C can build the full API + frontend end-to-end on day one, using all
  three mocks, then swap in real implementations as they land — no rewiring.

Whoever finishes their real implementation first: replace the mock function
body in their file, keep the function signature and return shape identical to
the contract, open a PR. Nothing downstream needs to change.

## Setup

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```
API docs at `http://localhost:8000/docs` (FastAPI auto-generates this — useful
for Track C to hand a live testable API to A and B immediately).

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Repo layout
```
backend/
  perception/        Track A — detection + colour + style
  recommender/        Track B — MCKP/DP + Greedy baseline
  explainability/      Track B — explanation generator
  store_locator/       Track C — Google Places wrapper
  api/                 Track C — FastAPI routes wiring all layers together
  db/                  Track C — SQLAlchemy models (see docs/CONTRACTS.md for schema)
frontend/               Track C — React (Vite) UI
data/                   dataset notes + prep scripts (see data/README.md)
docs/
  CONTRACTS.md          the JSON interfaces between layers — READ THIS FIRST
  ROADMAP.md            phased implementation plan
```

## Branching
- `main` — protected, PR only
- `feat/perception`, `feat/recommender`, `feat/app` — one per track
- Small, frequent PRs into `main` beat one giant PR at the end.

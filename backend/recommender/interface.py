"""
Track B owns this file.

Contract: see docs/CONTRACTS.md section 3.

Real implementation notes (per synopsis):
- Formulate as a Multi-Choice Knapsack Problem: exactly one item per required
  category, total price <= budget, maximise style/colour-compatibility score.
- Solve exactly via Dynamic Programming (dp_optimal).
- Also implement a Greedy baseline (highest compatibility-to-cost first) for
  the evaluation in Phase 3 of docs/ROADMAP.md.
- Keep both behind the same recommend() signature; add a `method` param.
"""

from typing import List, Dict


def recommend(
    style: str,
    palette: List[str],
    budget: float,
    catalog: List[Dict],
    method: str = "dp_optimal",
) -> dict:
    """
    MOCK IMPLEMENTATION — replace with real MCKP/DP solver + Greedy baseline.

    Args:
        style: detected room style label (from perception layer).
        palette: list of dominant hex colours (from perception layer).
        budget: user's total stated budget.
        catalog: list of catalog items, each matching docs/CONTRACTS.md section 2.
        method: "dp_optimal" or "greedy" — for the Phase 3 evaluation comparison.

    Returns:
        dict matching docs/CONTRACTS.md section 3.
    """
    selected = [
        {"item_id": "itm_00123", "category": "bed", "score": 0.88, "price": 24500},
        {"item_id": "itm_00456", "category": "lighting", "score": 0.79, "price": 3200},
    ]
    return {
        "selected_items": selected,
        "total_price": sum(i["price"] for i in selected),
        "compatibility_score": sum(i["score"] for i in selected) / len(selected),
        "method": method,
    }


def solve_dp(items_by_category: Dict[str, List[Dict]], budget: float) -> List[Dict]:
    """Real DP/MCKP solver — implement here. One item per category, maximise
    total compatibility score subject to sum(price) <= budget."""
    raise NotImplementedError("Track B: implement the DP table here")


def solve_greedy(items_by_category: Dict[str, List[Dict]], budget: float) -> List[Dict]:
    """Greedy baseline — highest compatibility-to-cost ratio first, for
    comparison against solve_dp() in the Phase 3 evaluation."""
    raise NotImplementedError("Track B: implement the greedy baseline here")

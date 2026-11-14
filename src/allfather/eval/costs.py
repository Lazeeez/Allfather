"""Conservative per-run monetary accounting shared by analysis and paper generation.

Recorded amounts are harness reports, not independently verified bills. An absent amount
is unknown. Local harness zero placeholders do not measure compute cost. Estimates must
carry an explicit basis and boundary; this module never guesses historical prices,
hardware counts or per-request tiers from an aggregate token count.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class Cost:
    usd: float | None
    state: Literal["recorded", "estimated", "unknown"]
    basis: str
    scope: str


def nonnegative(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def record_cost(row: dict) -> Cost:
    explicit = row.get("cost_accounting")
    if explicit is not None:
        if not isinstance(explicit, dict) or explicit.get("schema") != "run-cost-v1":
            raise ValueError("invalid cost_accounting schema")
        state, amount = explicit.get("state"), nonnegative(explicit.get("usd"))
        basis, scope = explicit.get("basis"), explicit.get("scope")
        if state not in ("recorded", "estimated", "unknown") or not all(
            isinstance(s, str) and s.strip() for s in (basis, scope)
        ):
            raise ValueError("cost accounting requires state, basis and scope")
        if (state == "unknown" and explicit.get("usd") is not None) or (
            state != "unknown" and amount is None
        ):
            raise ValueError("cost amount disagrees with its state")
        return Cost(amount, state, basis, scope)
    amount = nonnegative(row.get("cost_usd"))
    if amount is None:
        return Cost(None, "unknown", "missing_or_invalid_recorded_amount", "run_charge")
    if amount == 0 and str(row.get("system", "")).startswith(("website", "allfather", "swerank")):
        return Cost(None, "unknown", "legacy_local_zero_placeholder", "run_charge")
    return Cost(amount, "recorded", "harness_cost_usd; not bill-verified", "run_charge")


def summarize(costs: list[Cost]) -> dict:
    """Never substitute the known subset's mean for the complete cohort's mean."""
    states = Counter(c.state for c in costs)
    scopes = sorted({c.scope for c in costs})
    complete = bool(costs) and all(c.usd is not None for c in costs) and len(scopes) == 1
    subtotal = sum(c.usd for c in costs if c.usd is not None)
    return {
        "schema": "cost-summary-v1",
        "rows": len(costs),
        "states": dict(sorted(states.items())),
        "scopes": scopes,
        "complete": complete,
        "known_subtotal_usd": subtotal if len(scopes) <= 1 else None,
        "total_usd": subtotal if complete else None,
        "mean_usd": subtotal / len(costs) if complete else None,
        "basis_counts": dict(sorted(Counter(c.basis for c in costs).items())),
    }


def sum_costs(costs: list[Cost]) -> Cost:
    """Sum actually incurred components for a single evaluated issue."""
    summary = summarize(costs)
    scope = costs[0].scope if len(summary["scopes"]) == 1 else "mixed"
    if not summary["complete"]:
        return Cost(None, "unknown", "missing_component_or_incompatible_scopes", scope)
    state = "estimated" if any(c.state == "estimated" for c in costs) else "recorded"
    return Cost(summary["total_usd"], state, "sum_of_selected_components", scope)


def cost_from_scored(row: dict) -> Cost:
    """Accept the shared serialized record; numeric fallback supports older callers."""
    if "cost_accounting" in row:
        return Cost(**row["cost_accounting"])
    return record_cost({"cost_usd": row.get("cost")})


def selected_costs(ref: dict, other: dict, ids: list[str], selected: list[bool]) -> dict:
    if len(ids) != len(set(ids)) or len(ids) != len(selected):
        raise ValueError("invalid cascade cohort")
    totals = [
        sum_costs([cost_from_scored(ref[q]), *([cost_from_scored(other[q])] if send else [])])
        for q, send in zip(ids, selected, strict=True)
    ]
    return summarize(totals) | {
        "ids": ids,
        "selected_ids": [q for q, send in zip(ids, selected, strict=True) if send],
    }


def serialize(cost: Cost) -> dict:
    return asdict(cost)

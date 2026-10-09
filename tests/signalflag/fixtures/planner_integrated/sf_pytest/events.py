"""Rows -> events. Pure functions; see the brief's Events table."""
from __future__ import annotations

from .records import TestRecord

NEAR_MISS_FRACTION = 0.10   # provisional: 10% of the limit


def detect(rec: TestRecord) -> list[dict]:
    r = rec.planner_result
    if r is None:
        excerpt = (rec.message or "no Result recorded")[-1500:]
        return [_event("Harness failure", f"{rec.outcome}: test produced no planner Result",
                       "FAIL_BLOCK", ["harness"],
                       [{"name": "Log excerpt", "type": "text", "value": excerpt}])]
    events = []
    ratio_m = [{"name": "Detour ratio", "type": "scalar", "value": r["detour_ratio"]},
               {"name": "Limit", "type": "scalar", "value": r["ratio_limit"]}]
    clr_m = [{"name": "Min clearance", "type": "scalar", "value": r["min_clearance_m"], "unit": "m"},
             {"name": "Limit", "type": "scalar", "value": r["clearance_limit"], "unit": "m"}]
    if r["detour_ratio"] >= r["ratio_limit"]:
        events.append(_event("Detour limit crossed",
                             f"Detour ratio {r['detour_ratio']:.3f} >= {r['ratio_limit']}",
                             "FAIL_BLOCK", ["threshold"], ratio_m))
    elif r["ratio_margin"] < NEAR_MISS_FRACTION * r["ratio_limit"]:
        events.append(_event("Near-miss: detour",
                             f"Detour ratio {r['detour_ratio']:.3f}, margin {r['ratio_margin']:.3f} to {r['ratio_limit']}",
                             "FAIL_WARN", ["near-miss"], ratio_m))
    if r["min_clearance_m"] <= r["clearance_limit"]:
        events.append(_event("Clearance limit crossed",
                             f"Min clearance {r['min_clearance_m']:.3f} m <= {r['clearance_limit']} m",
                             "FAIL_BLOCK", ["threshold"], clr_m))
    elif r["clearance_margin"] < NEAR_MISS_FRACTION * r["clearance_limit"]:
        events.append(_event("Near-miss: clearance",
                             f"Min clearance {r['min_clearance_m']:.3f} m, margin {r['clearance_margin']:.3f} m",
                             "FAIL_WARN", ["near-miss"], clr_m))
    return events


def _event(name, description, status, tags, metrics):
    return {"name": name, "description": description, "status": status, "tags": tags, "metrics": metrics}

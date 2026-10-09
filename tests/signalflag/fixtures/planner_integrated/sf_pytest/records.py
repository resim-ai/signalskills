"""Rows recorded per test. Pure Python; never imports signalflag."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestRecord:
    name: str                         # pytest item name, e.g. test_plan[corridor]
    start_ns: int
    outcome: str = "passed"           # passed | failed | error | skipped
    duration_s: float = 0.0
    message: str = ""
    planner_result: dict[str, Any] | None = None
    obstacles: list[tuple[float, float]] = field(default_factory=list)


def planner_row(scenario: str, result: Any, obstacles, max_detour: float, min_clearance: float) -> dict[str, Any]:
    ratio = result.path_length_m / result.straight_m
    return {
        "scenario": scenario,
        "path_length_m": float(result.path_length_m),
        "straight_m": float(result.straight_m),
        "detour_ratio": float(ratio),
        "ratio_limit": float(max_detour),
        "ratio_margin": float(max_detour - ratio),
        "min_clearance_m": float(result.min_clearance_m),
        "clearance_limit": float(min_clearance),
        "clearance_margin": float(result.min_clearance_m - min_clearance),
        "goal_x": float(result.straight_m),
        "obstacle_count": len(obstacles),
        "passed": bool(ratio < max_detour and result.min_clearance_m > min_clearance),
    }

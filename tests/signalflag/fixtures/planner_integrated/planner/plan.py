import math
from dataclasses import dataclass

SCENARIOS = {"open": [], "one_box": [(5, 0.4)], "corridor": [(3, 0.9), (6, -0.9)], "clutter": [(2, 0.2), (4, -0.2), (6, 0.1)]}

@dataclass
class Result:
    path_length_m: float
    straight_m: float
    min_clearance_m: float

def plan(scenario: str, goal_x: float = 8.0) -> Result:
    obstacles = SCENARIOS[scenario]
    detour = sum(0.6 / max(abs(y), 0.1) * 0.1 for _, y in obstacles)
    clearance = min((abs(y) + 0.1 for _, y in obstacles), default=5.0)
    return Result(goal_x * (1 + detour), goal_x, clearance)

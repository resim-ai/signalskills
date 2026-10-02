"""Sample lateral offsets over a horizon, pick the cheapest collision-free one."""
from dataclasses import dataclass
import numpy as np

LANE_W = 3.6

@dataclass
class Plan:
    offsets_m: np.ndarray
    max_lat_accel: float
    min_gap_m: float
    stop_s: float | None

def plan(speed: float, target_lane: int = 0, obstacle_s: float | None = None, lead_gap_m: float = 50.0) -> Plan:
    s = np.linspace(0, speed * 6, 61)
    shift = target_lane * LANE_W
    u = np.clip(s / max(speed * 4, 1e-3), 0, 1)
    off = shift * (10 * u**3 - 15 * u**4 + 6 * u**5)
    curv = np.gradient(np.gradient(off, s), s)
    lat_acc = float(np.max(np.abs(curv)) * speed**2)
    stop = None
    if obstacle_s is not None:
        decel = speed**2 / (2 * max(obstacle_s - 2.0, 0.1))
        stop = obstacle_s - 2.0 if decel <= 3.5 else None
    return Plan(off, lat_acc, lead_gap_m - speed * 1.2, stop)

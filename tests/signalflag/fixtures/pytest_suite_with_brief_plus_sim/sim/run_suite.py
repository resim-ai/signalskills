"""Closed-loop sim: a unicycle tracks the planned path through each scenario's obstacles.

python sim/run_suite.py [--seed N] [--stamp YYYYmmddTHHMMSS]
writes sim/runs/<stamp>/<scenario>/result.json and trajectory.csv
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from planner.plan import SCENARIOS, plan

DT, MAX_T = 0.1, 30.0

def simulate(scenario: str, rng) -> tuple[dict, np.ndarray]:
    r = plan(scenario)
    speed = 1.0
    x, lat, rows, t = 0.0, 0.0, [], 0.0
    min_clear = 9.0
    while x < r.straight_m and t < MAX_T:
        lat += -0.6 * lat * DT + rng.normal(0, 0.03)
        x += speed * DT * r.straight_m / r.path_length_m
        for ox, oy in SCENARIOS[scenario]:
            if abs(x - ox) < 0.5:
                min_clear = min(min_clear, abs(oy - lat) - 0.2)
        t += DT
        rows.append((round(t, 2), round(x, 4), round(lat, 4)))
    res = {"scenario": scenario, "reached_goal": bool(x >= r.straight_m), "time_to_goal_s": round(t, 2),
           "min_clearance_m": round(min(min_clear, 5.0), 4),
           "max_tracking_error_m": round(float(max(abs(v[2]) for v in rows)), 4), "planned_path_m": round(r.path_length_m, 3)}
    return res, np.array(rows)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stamp", default=time.strftime("%Y%m%dT%H%M%S"))
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    for scenario in SCENARIOS:
        out = Path(__file__).parent / "runs" / a.stamp / scenario
        out.mkdir(parents=True, exist_ok=True)
        res, traj = simulate(scenario, rng)
        (out / "result.json").write_text(json.dumps(res, indent=2) + "\n")
        np.savetxt(out / "trajectory.csv", traj, delimiter=",", header="t_s,x_m,lateral_m", comments="", fmt="%.4f")
        print(scenario, res)

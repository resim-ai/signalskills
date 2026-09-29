"""Toy point-robot suite. One folder per scenario under runs/."""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

SCENARIOS = {"straight": [(10, 0)], "corner": [(5, 0), (5, 5)], "slalom": [(3, 1), (6, -1), (9, 1)]}
STEPS, DT = 150, 0.1

def run(name, waypoints, gain, out):
    pos, wp, rows = np.zeros(2), 0, []
    (out / "frames").mkdir(parents=True, exist_ok=True)
    for k in range(STEPS):
        target = np.array(waypoints[wp], float)
        err = target - pos
        if np.linalg.norm(err) < 0.3 and wp < len(waypoints) - 1:
            wp += 1
        pos = pos + gain * err * DT
        rows.append((int(k * DT * 1e9), *pos, float(np.linalg.norm(err))))
        img = Image.new("RGB", (120, 120), "white")
        x, y = 10 + pos[0] * 9, 60 - pos[1] * 9
        ImageDraw.Draw(img).ellipse([x - 3, y - 3, x + 3, y + 3], fill="red")
        img.save(out / "frames" / f"{k:04d}.png")
    np.savetxt(out / "telemetry.csv", rows, delimiter=",", header="t_ns,x,y,err_m", comments="")
    final = float(np.linalg.norm(np.array(waypoints[-1]) - pos))
    (out / "results.json").write_text(json.dumps({"scenario": name, "gain": gain,
        "final_error_m": final, "sim_duration_s": STEPS * DT}))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain", type=float, default=0.5)
    a = ap.parse_args()
    for name, w in SCENARIOS.items():
        run(name, w, a.gain, Path("runs") / name)

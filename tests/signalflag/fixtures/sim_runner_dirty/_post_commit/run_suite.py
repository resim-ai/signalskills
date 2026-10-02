"""Toy point-robot suite. One folder per run: runs/<YYYYmmdd-HHMMSS>/<scenario>/."""
import argparse, json, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

SCENARIOS = {"straight": [(10, 0)], "corner": [(5, 0), (5, 5)], "slalom": [(3, 1), (6, -1), (9, 1)]}
STEPS, DT = 150, 0.1
FRAME_EVERY = 5  # was every step; too many files

def run(name, waypoints, gain, out, kd=0.0):
    pos, wp, rows, prev = np.zeros(2), 0, [], None
    (out / "frames").mkdir(parents=True, exist_ok=True)
    for k in range(STEPS):
        target = np.array(waypoints[wp], float)
        err = target - pos
        if np.linalg.norm(err) < 0.3 and wp < len(waypoints) - 1:
            wp += 1
        derr = np.zeros(2) if prev is None else (err - prev) / DT
        prev = err
        pos = pos + (gain * err + kd * derr) * DT
        rows.append((int(k * DT * 1e9), *pos, float(np.linalg.norm(err))))
        if k % FRAME_EVERY == 0:
            img = Image.new("RGB", (120, 120), "white")
            x, y = 10 + pos[0] * 9, 60 - pos[1] * 9
            ImageDraw.Draw(img).ellipse([x - 3, y - 3, x + 3, y + 3], fill="red")
            img.save(out / "frames" / f"{k:04d}.png")
    np.savetxt(out / "telemetry.csv", rows, delimiter=",", header="t_ns,x,y,err_m", comments="")
    final = float(np.linalg.norm(np.array(waypoints[-1]) - pos))
    (out / "results.json").write_text(json.dumps({"scenario": name, "gain": gain, "kd": kd,
        "final_error_m": final, "sim_duration_s": STEPS * DT}))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gain", type=float, default=0.5)
    ap.add_argument("--kd", type=float, default=0.0)
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for name, w in SCENARIOS.items():
        run(name, w, a.gain, Path("runs") / stamp / name, a.kd)

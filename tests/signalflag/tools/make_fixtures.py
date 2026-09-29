"""Deterministic fixtures for the SignalFlag skill scenarios. `python make_fixtures.py <dest>`."""
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


def rl_project(dest: Path) -> Path:
    root = dest / "rl_project"
    _write(root / "eval_checkpoint.py", '''
        """Evaluate one checkpoint over 5 seeds. Writes evals/<stamp>/episodes.csv."""
        import sys, time
        from pathlib import Path
        import numpy as np, pandas as pd

        def evaluate(ckpt: str, seeds=range(5)) -> pd.DataFrame:
            step = int(ckpt.rsplit("_", 1)[-1])
            rng = np.random.default_rng(step)
            ret = 50 + step / 1000 + rng.normal(0, 5, len(seeds))
            return pd.DataFrame({"seed": list(seeds), "return": ret,
                                 "success": ret > 70, "episode_len": rng.integers(200, 400, len(seeds))})

        def main(ckpt: str) -> Path:
            out = Path("evals") / time.strftime("%Y%m%dT%H%M%S")
            out.mkdir(parents=True)
            evaluate(ckpt).to_csv(out / "episodes.csv", index=False)
            (out / "log.txt").write_text(f"loaded {ckpt}\\n")
            return out

        if __name__ == "__main__":
            print(main(sys.argv[1]))
        ''')
    _write(root / "tests" / "test_eval.py", '''
        import sys; sys.path.insert(0, ".")
        from eval_checkpoint import evaluate

        def test_five_seeds():
            assert len(evaluate("checkpoints/ckpt_10000")) == 5
        ''')
    for i, step in enumerate([10000, 20000, 30000, 40000]):
        run = root / "evals" / f"20260901T0{i}0000"
        run.mkdir(parents=True)
        rng = np.random.default_rng(step)
        ret = 50 + step / 1000 + rng.normal(0, 5, 5)
        pd.DataFrame({"seed": range(5), "return": ret, "success": ret > 70,
                      "episode_len": rng.integers(200, 400, 5)}).to_csv(run / "episodes.csv", index=False)
        if step != 30000:
            (run / "log.txt").write_text(f"loaded checkpoints/ckpt_{step}\n")
    return root


def pytest_suite(dest: Path) -> Path:
    root = dest / "pytest_suite"
    _write(root / "pyproject.toml", '''
        [project]
        name = "planner"
        version = "0.1.0"
        dependencies = []

        [project.optional-dependencies]
        dev = ["pytest"]
        ''')
    _write(root / "conftest.py", "")  # puts the root on sys.path so tests import planner
    _write(root / "planner" / "__init__.py", "")
    _write(root / "planner" / "plan.py", '''
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
        ''')
    _write(root / "tests" / "test_planner.py", '''
        import pytest
        from planner.plan import plan

        @pytest.mark.parametrize("scenario", ["open", "one_box", "corridor", "clutter"])
        def test_plan(scenario):
            r = plan(scenario)
            assert r.path_length_m < 1.2 * r.straight_m
            assert r.min_clearance_m > 0.25
        ''')
    return root


def parquet_dump(dest: Path) -> Path:
    root = dest / "parquet_dump"
    def drive(seed: int, extra: bool) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        n = 600
        t = (np.arange(n) * 1e8).astype("int64")
        cmd = np.clip(np.cumsum(rng.normal(0, 0.05, n)), 0, 2)
        df = pd.DataFrame({"t_ns": t, "speed_mps": cmd + rng.normal(0, 0.05, n), "cmd_speed_mps": cmd,
                           "battery_pct": np.linspace(95, 80, n),
                           "mode": np.where(cmd > 0.1, "AUTO", "IDLE")})
        if extra:
            df["motor_temp_c"] = 40 + np.linspace(0, 15, n)
        return df
    (root / "telemetry").mkdir(parents=True)
    (root / "telemetry_v2").mkdir(parents=True)
    for i in (1, 2, 3):
        drive(i, False).to_parquet(root / "telemetry" / f"drive_0{i}.parquet")
    drive(4, True).to_parquet(root / "telemetry_v2" / "drive_04.parquet")
    return root


def sim_runner(dest: Path) -> Path:
    root = dest / "sim_runner"
    _write(root / "run_suite.py", '''
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
        ''')
    return root


if __name__ == "__main__":
    dest = Path(sys.argv[1])
    for make in (rl_project, pytest_suite, parquet_dump, sim_runner):
        print(make(dest))

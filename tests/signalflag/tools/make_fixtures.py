"""Deterministic fixtures for the SignalFlag skill scenarios. `python make_fixtures.py <dest>`."""
import csv
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


# ---- helpers for the robotics fixtures below ----

def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def _csv(path: Path, rows) -> None:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue())


def _ns(*ymdhms) -> int:
    """UTC datetime -> epoch ns."""
    return int(datetime(*ymdhms, tzinfo=timezone.utc).timestamp()) * 1_000_000_000


def _hdr(t_ns: int, frame: str) -> dict:
    return {"stamp": {"sec": int(t_ns // 1_000_000_000), "nanosec": int(t_ns % 1_000_000_000)}, "frame_id": frame}


def _r(x, n=3):
    return round(float(x), n)


def _quat_z(yaw: float) -> dict:
    return {"x": 0.0, "y": 0.0, "z": _r(np.sin(yaw / 2), 4), "w": _r(np.cos(yaw / 2), 4)}


def _jsonschema(v) -> dict:
    if isinstance(v, bool):
        return {"type": "boolean"}
    if isinstance(v, int):
        return {"type": "integer"}
    if isinstance(v, float):
        return {"type": "number"}
    if isinstance(v, str):
        return {"type": "string"}
    if isinstance(v, list):
        items = {}
        for x in v:
            items = _merge_schema(items, _jsonschema(x))
        return {"type": "array", "items": items}
    return {"type": "object", "properties": {k: _jsonschema(x) for k, x in v.items()}}


def _merge_schema(a: dict, b: dict) -> dict:
    if not a:
        return b
    if a.get("type") == "object" and b.get("type") == "object":
        props = dict(a["properties"])
        for k, v in b["properties"].items():
            props[k] = _merge_schema(props.get(k, {}), v)
        return {"type": "object", "properties": props}
    if a.get("type") == "array" and b.get("type") == "array":
        return {"type": "array", "items": _merge_schema(a["items"], b["items"])}
    if {a.get("type"), b.get("type")} == {"integer", "number"}:
        return {"type": "number"}
    return a


def _write_mcap(path: Path, records, library: str = "rosbag2 mcap") -> None:
    """records: (topic, schema_name, log_time_ns, msg_dict). JSON messages, jsonschema schemas, no compression.
    log_time None = declare the channel (schema from the example msg) without writing a message."""
    from mcap.writer import CompressionType, Writer
    schemas: dict = {}
    for topic, sname, _, msg in records:
        prev = schemas.get(topic, (sname, {}))[1]
        schemas[topic] = (sname, _merge_schema(prev, _jsonschema(msg)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w = Writer(f, compression=CompressionType.NONE)
        w.start(profile="", library=library)
        ids = {}
        for topic, (sname, sch) in schemas.items():
            sid = w.register_schema(name=sname, encoding="jsonschema",
                                    data=json.dumps({"title": sname, **sch}, sort_keys=True).encode())
            ids[topic] = w.register_channel(topic=topic, message_encoding="json", schema_id=sid)
        seq: dict = {}
        for topic, _, t, msg in sorted((r for r in records if r[2] is not None), key=lambda r: r[2]):
            seq[topic] = seq.get(topic, 0) + 1
            w.add_message(ids[topic], log_time=int(t), data=json.dumps(msg, separators=(",", ":")).encode(),
                          publish_time=int(t), sequence=seq[topic])
        w.finish()


def _mp4(path: Path, frames: np.ndarray, fps: int) -> None:
    """frames: (n, h, w, 3) uint8 -> small h264 mp4 via ffmpeg (content-deterministic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n, h, w, _ = frames.shape
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                    "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                    "-pix_fmt", "yuv420p", "-threads", "1", "-bitexact", "-fflags", "+bitexact",
                    "-flags:v", "+bitexact", "-map_metadata", "-1", str(path)],
                   input=np.ascontiguousarray(frames, dtype=np.uint8).tobytes(), check=True)


def _run_py(cwd: Path, *args: str, env: dict | None = None) -> None:
    """Run a fixture's own script so committed artifacts are exactly what its code writes."""
    subprocess.run([sys.executable, *args], cwd=cwd, check=True, env={**os.environ, "PYTHONHASHSEED": "0", **(env or {})},
                   stdout=subprocess.DEVNULL)


def _clean_pycache(root: Path) -> None:
    for p in sorted(root.rglob("__pycache__"), reverse=True):
        shutil.rmtree(p)
    for p in root.rglob(".pytest_cache"):
        shutil.rmtree(p)


def _derive(base, dest: Path, name: str) -> Path:
    """Build fixture `base` and copy it to dest/name as the starting point of a variant."""
    root = dest / name
    if root.exists():
        shutil.rmtree(root)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(base(Path(tmp)), root)
    return root


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


# ---- perception replay (ros2_replay, monorepo/perception) ----

_REPLAY_SCENARIOS = {
    # name: (seed, recording start, actors as (class, x0, y0, vx, vy) in the ego frame at t0)
    "urban_intersection_01": (11, (2026, 3, 14, 15, 2, 10), [("car", 18, -3.5, -6, 0), ("car", -25, 3.5, 7, 0),
                                                             ("pedestrian", 9, 8, 0, -1.2), ("bicycle", 30, 6, -4, 0)]),
    "highway_cut_in_02": (12, (2026, 4, 2, 10, 41, 0), [("car", 25, 3.6, 9.5, -0.6), ("truck", 45, 0, 8.5, 0),
                                                        ("car", -15, -3.6, 11, 0)]),
    "parking_lot_03": (13, (2026, 5, 19, 8, 12, 30), [("car", 10, 5, 0, -0.8), ("pedestrian", 6, -4, 0.3, 0.9),
                                                      ("pedestrian", 14, 2, -0.8, 0), ("traffic_cone", 5, 1.5, 0, 0)]),
    "night_ped_crossing_04": (14, (2026, 6, 7, 21, 30, 5), [("pedestrian", 12, 7, 0, -1.4), ("pedestrian", 13, 8, 0, -1.1),
                                                            ("car", 40, -3.5, -9, 0)]),
    "roundabout_merge_05": (15, (2026, 7, 1, 13, 5, 0), [("car", 15, 8, -2, -2), ("bus", 30, -6, -3, 1.0)]),
    "construction_zone_06": (16, (2026, 7, 22, 9, 47, 30), [("traffic_cone", 12, 2.0, 0, 0), ("traffic_cone", 18, 2.2, 0, 0),
                                                            ("truck", 35, 3.5, 2, 0), ("pedestrian", 22, 4.5, 0.2, 0)]),
}
_SIZES = {"car": (4.6, 1.9, 1.6), "truck": (9.5, 2.5, 3.4), "bus": (12.0, 2.6, 3.2), "pedestrian": (0.6, 0.6, 1.75),
          "bicycle": (1.8, 0.6, 1.4), "traffic_cone": (0.4, 0.4, 0.7)}
_EGO_SPEED = 8.0


def _replay_scenario_bags(root: Path, names) -> None:
    """Input bags: what the vehicle recorded (vehicle odom, a tiny lidar cloud, camera info)."""
    import base64
    for name in names:
        seed, start, _ = _REPLAY_SCENARIOS[name]
        rng = np.random.default_rng(seed)
        t0, recs = _ns(*start), []
        for k in range(120):  # 12 s at 10 Hz
            t = t0 + k * 100_000_000
            recs.append(("/vehicle/odom", "nav_msgs/msg/Odometry", t, {
                "header": _hdr(t, "odom"), "child_frame_id": "base_link",
                "pose": {"pose": {"position": {"x": _r(k * 0.1 * _EGO_SPEED), "y": 0.0, "z": 0.0}, "orientation": _quat_z(0.0)}},
                "twist": {"twist": {"linear": {"x": _r(_EGO_SPEED + rng.normal(0, 0.1)), "y": 0.0, "z": 0.0},
                                    "angular": {"x": 0.0, "y": 0.0, "z": _r(rng.normal(0, 0.01), 4)}}}}))
            pts = rng.normal(0, 10, (8, 4)).astype("float32")
            recs.append(("/lidar/points", "sensor_msgs/msg/PointCloud2", t + 2_000_000, {
                "header": _hdr(t, "lidar_top"), "height": 1, "width": 8, "point_step": 16, "row_step": 128,
                "fields": [{"name": n, "offset": 4 * i, "datatype": 7, "count": 1} for i, n in enumerate(["x", "y", "z", "intensity"])],
                "is_bigendian": False, "is_dense": True, "data": base64.b64encode(pts.tobytes()).decode()}))
            if k % 10 == 0:
                recs.append(("/camera/front/camera_info", "sensor_msgs/msg/CameraInfo", t + 5_000_000, {
                    "header": _hdr(t, "camera_front"), "height": 1080, "width": 1920, "distortion_model": "plumb_bob",
                    "k": [1266.4, 0.0, 960.0, 0.0, 1266.4, 540.0, 0.0, 0.0, 1.0]}))
        _write_mcap(root / "scenarios" / f"{name}.mcap", recs)


def _replay_outputs(root: Path, names, replay_day) -> None:
    """outputs/<scenario>/output.mcap: what perception published during replay. header.stamp = bag (sim) time,
    log_time = wall clock of the replay."""
    for i, name in enumerate(names):
        seed, start, actors = _REPLAY_SCENARIOS[name]
        rng = np.random.default_rng(seed + 100)
        t0, wall0 = _ns(*start), _ns(*replay_day) + i * 900_000_000_000
        recs = []
        for k in range(120):
            t, wall = t0 + k * 100_000_000, wall0 + k * 100_000_000 + 35_000_000
            dets, tracks = [], []
            for j, (cls, x0, y0, vx, vy) in enumerate(actors):
                x, y = x0 + (vx - _EGO_SPEED) * k * 0.1, y0 + vy * k * 0.1  # ego frame, ego at _EGO_SPEED
                miss = rng.random() < (0.3 if "night" in name and cls == "pedestrian" else 0.06)
                if np.hypot(x, y) > 60 or miss:
                    continue
                size = _SIZES[cls]
                dets.append({"class_id": cls, "score": _r(np.clip(rng.normal(0.82, 0.08), 0.3, 0.99)),
                             "bbox": {"center": {"x": _r(x + rng.normal(0, 0.15)), "y": _r(y + rng.normal(0, 0.15)),
                                                 "z": _r(size[2] / 2), "yaw": _r(np.arctan2(vy, vx) if (vx or vy) else 0.0)},
                                      "size": {"l": size[0], "w": size[1], "h": size[2]}}})
                if k > 2:
                    tracks.append({"track_id": 100 * i + j + 1, "class_id": cls, "position": {"x": _r(x), "y": _r(y)},
                                   "velocity": {"x": _r(vx - _EGO_SPEED + rng.normal(0, 0.2)), "y": _r(vy + rng.normal(0, 0.2))},
                                   "age_s": _r((k - 2) * 0.1, 1), "confidence": _r(np.clip(rng.normal(0.85, 0.05), 0, 1))})
            recs.append(("/perception/detections", "acme_perception_msgs/msg/Detection3DArray", wall,
                         {"header": _hdr(t, "base_link"), "detections": dets}))
            recs.append(("/perception/tracks", "acme_perception_msgs/msg/TrackArray", wall + 8_000_000,
                         {"header": _hdr(t, "base_link"), "tracks": tracks}))
        _write_mcap(root / "outputs" / name / "output.mcap", recs)
        (root / "outputs" / name / "replay.log").write_text(
            f"[replay] scenario={name} bag=/scenarios/{name}.mcap rate=1.0 clock=on\n"
            f"[replay] recorded /perception/detections /perception/tracks -> /outputs/{name}/output.mcap\n"
            f"[replay] done: exit 0\n")


def _replay_harness(root: Path, names, image: str) -> None:
    _write(root / "compose.yaml", f'''
        # Perception replay: `docker compose --profile replay up`
        name: perception-replay

        x-ros: &ros
          network_mode: host
          ipc: host
          environment:
            ROS_DOMAIN_ID: "42"
            RMW_IMPLEMENTATION: rmw_cyclonedds_cpp

        services:
          perception:
            <<: *ros
            image: {image}
            profiles: [replay]
            command: ros2 launch perception_bringup replay.launch.py use_sim_time:=true
            volumes:
              - ./config:/opt/perception/config:ro

          replay:
            <<: *ros
            image: registry.acme.dev/tools/ros2-replay:humble-1.4.0
            profiles: [replay]
            depends_on: [perception]
            command: python3 /replay/run_replay.py --scenarios /scenarios --out /outputs
            volumes:
              - ./replay:/replay:ro
              - ./scenarios:/scenarios:ro
              - ./outputs:/outputs
        ''')
    _write(root / "replay" / "run_replay.py", '''
        """Play every scenario bag through the running perception stack and record what it publishes.

        Runs inside the `replay` container. For each scenarios/<name>.mcap writes
          outputs/<name>/output.mcap   (/perception/detections, /perception/tracks)
          outputs/<name>/replay.log
        """
        import argparse, shutil, signal, subprocess, time
        from pathlib import Path

        TOPICS = ["/perception/detections", "/perception/tracks"]

        def replay(bag: Path, out_root: Path) -> None:
            out = out_root / bag.stem
            shutil.rmtree(out, ignore_errors=True)
            log = [f"[replay] scenario={bag.stem} bag={bag} rate=1.0 clock=on"]
            rec = subprocess.Popen(["ros2", "bag", "record", "-s", "mcap", "--use-sim-time", "-o", str(out / "rec"), *TOPICS])
            time.sleep(2.0)  # let the recorder discover the topics
            play = subprocess.run(["ros2", "bag", "play", str(bag), "--clock", "--rate", "1.0"])
            time.sleep(1.0)
            rec.send_signal(signal.SIGINT)
            rec.wait(timeout=30)
            (out / "rec" / "rec_0.mcap").rename(out / "output.mcap")
            shutil.rmtree(out / "rec")
            log.append(f"[replay] recorded {' '.join(TOPICS)} -> {out / 'output.mcap'}")
            log.append(f"[replay] done: exit {play.returncode}")
            (out / "replay.log").write_text("\\n".join(log) + "\\n")

        if __name__ == "__main__":
            ap = argparse.ArgumentParser()
            ap.add_argument("--scenarios", type=Path, default=Path("scenarios"))
            ap.add_argument("--out", type=Path, default=Path("outputs"))
            a = ap.parse_args()
            for bag in sorted(a.scenarios.glob("*.mcap")):
                replay(bag, a.out)
        ''')
    _write(root / "config" / "perception.yaml", '''
        detector:
          model: centerpoint_pillar
          score_threshold: 0.3
          classes: [car, truck, bus, pedestrian, bicycle, traffic_cone]
        tracker:
          type: multi_hypothesis
          max_age_s: 1.5
          min_hits: 3
        ''')
    _replay_scenario_bags(root, names)


def ros2_replay(dest: Path) -> Path:
    root = dest / "ros2_replay"
    names = ["urban_intersection_01", "highway_cut_in_02", "parking_lot_03", "night_ped_crossing_04"]
    _replay_harness(root, names, "registry.acme.dev/perception/stack:2026.09.3")
    _write(root / "README.md", '''
        # perception-replay

        Replays recorded scenario bags through the perception stack (ROS 2 Humble) and records what it publishes.

        ```
        docker compose --profile replay up
        ```

        - `scenarios/*.mcap`: input bags (vehicle odom, lidar, camera info).
        - `outputs/<scenario>/output.mcap`: `/perception/detections` and `/perception/tracks` from the last replay
          (overwritten each run).
        - The perception image is pinned in `compose.yaml`; bump the tag to test a new stack build.

        TODO: grade outputs against labels (not built yet).
        ''')
    _replay_outputs(root, names, (2026, 9, 29, 16, 0, 0))
    return root


def perception_det(dest: Path) -> Path:
    import pickle
    root = dest / "perception_det"
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # centerpoint-v3

        3D detector training + evaluation on the internal val splits (`day`, `night`, `rain`).

        Training (on the cluster) saves `runs/centerpoint_v3/ckpt_<epoch>.pth` every 5 epochs. Evaluate one:

        ```
        python eval.py --ckpt runs/centerpoint_v3/ckpt_25.pth
        ```

        Writes `eval/<epoch>/metrics_<split>.json` per split (nuScenes-style: mAP, NDS, TP errors, per-class AP).
        ''')
    _write(root / "configs" / "centerpoint_v3.yaml", '''
        model: centerpoint_pillar
        voxel_size: [0.2, 0.2, 8.0]
        point_cloud_range: [-51.2, -51.2, -5.0, 51.2, 51.2, 3.0]
        classes: [car, truck, bus, pedestrian, bicycle, traffic_cone]
        train:
          epochs: 30
          lr: 0.001
          batch_size: 16
          save_every: 5
        eval:
          splits: [day, night, rain]
          dist_ths: [0.5, 1.0, 2.0, 4.0]
        ''')
    _write(root / "det3d_eval" / "__init__.py", "")
    _write(root / "det3d_eval" / "scoring.py", '''
        """Detection scoring on the val splits (nuScenes detection metrics)."""
        import pickle, zipfile
        import numpy as np

        SPLITS = {"day": 2410, "night": 1180, "rain": 760}  # val samples per split
        CLASSES = ["car", "truck", "bus", "pedestrian", "bicycle", "traffic_cone"]
        CLASS_DIFFICULTY = {"car": 1.25, "truck": 0.85, "bus": 0.95, "pedestrian": 1.1, "bicycle": 0.7, "traffic_cone": 1.0}
        DIST_THS = [0.5, 1.0, 2.0, 4.0]

        def load_checkpoint(path: str) -> dict:
            try:
                import torch
                return torch.load(path, map_location="cpu")
            except ImportError:  # CPU box without torch: read the metadata only
                with zipfile.ZipFile(path) as z:
                    return pickle.loads(z.read("archive/data.pkl"))

        def _split_map(epoch: int, split: str) -> float:
            base = {"day": 0.63, "night": 0.52, "rain": 0.48}[split]
            m = base - 0.24 * np.exp(-epoch / 8)
            if split == "night" and epoch > 15:  # night degrades as day overfits
                m -= 0.011 * (epoch - 15)
            return m

        def evaluate_split(ckpt: dict, split: str) -> dict:
            epoch = ckpt["epoch"]
            rng = np.random.default_rng(epoch * 31 + len(split))
            m = _split_map(epoch, split) + rng.normal(0, 0.004)
            label_aps, mean_dist_aps = {}, {}
            for c in CLASSES:
                ap_c = float(np.clip(m * CLASS_DIFFICULTY[c] + rng.normal(0, 0.01), 0, 1))
                if split == "night" and c in ("pedestrian", "bicycle"):
                    ap_c *= 0.8
                label_aps[c] = {str(th): round(float(np.clip(ap_c * (0.7 + 0.1 * i), 0, 1)), 4) for i, th in enumerate(DIST_THS)}
                mean_dist_aps[c] = round(float(np.mean(list(label_aps[c].values()))), 4)
            mean_ap = float(np.mean(list(mean_dist_aps.values())))
            tp = {"trans_err": 0.30 - 0.1 * m, "scale_err": 0.26, "orient_err": 0.42 - 0.2 * m,
                  "vel_err": 0.33 - 0.1 * m, "attr_err": 0.19}
            tp = {k: round(float(v + rng.normal(0, 0.005)), 4) for k, v in tp.items()}
            nds = (5 * mean_ap + sum(1 - min(1, v) for v in tp.values())) / 10
            return {"mean_ap": round(mean_ap, 4), "nd_score": round(float(nds), 4), "tp_errors": tp,
                    "label_aps": label_aps, "mean_dist_aps": mean_dist_aps, "num_samples": SPLITS[split]}
        ''')
    _write(root / "eval.py", '''
        """Evaluate one checkpoint on the val splits. Writes eval/<epoch>/metrics_<split>.json."""
        import argparse, json, re
        from pathlib import Path
        from det3d_eval.scoring import SPLITS, evaluate_split, load_checkpoint

        def main() -> None:
            ap = argparse.ArgumentParser()
            ap.add_argument("--ckpt", required=True)
            ap.add_argument("--splits", nargs="+", default=list(SPLITS), choices=list(SPLITS))
            ap.add_argument("--out", type=Path, default=Path("eval"))
            a = ap.parse_args()
            epoch = int(re.search(r"ckpt_(\\d+)\\.pth$", a.ckpt).group(1))
            ckpt = load_checkpoint(a.ckpt)
            out = a.out / str(epoch)
            out.mkdir(parents=True, exist_ok=True)
            for split in a.splits:
                m = {"split": split, "epoch": epoch, "checkpoint": a.ckpt, **evaluate_split(ckpt, split)}
                (out / f"metrics_{split}.json").write_text(json.dumps(m, indent=2) + "\\n")
                print(f"epoch {epoch} {split:6s} mAP {m['mean_ap']:.4f} NDS {m['nd_score']:.4f}")

        if __name__ == "__main__":
            main()
        ''')
    ck = root / "runs" / "centerpoint_v3"
    ck.mkdir(parents=True)
    log = []
    for epoch in range(5, 31, 5):
        info = zipfile.ZipInfo("archive/data.pkl", date_time=(2026, 9, 10, 0, 0, 0))
        with zipfile.ZipFile(ck / f"ckpt_{epoch}.pth", "w") as z:
            z.writestr(info, pickle.dumps({"epoch": epoch, "arch": "centerpoint_pillar", "optimizer": "adamw"}, protocol=4))
            z.writestr(zipfile.ZipInfo("archive/version", date_time=(2026, 9, 10, 0, 0, 0)), "3\n")
        for e in range(epoch - 4, epoch + 1):
            log.append(f"epoch {e:2d} loss {2.9 * np.exp(-e / 9) + 0.6:.4f} lr {0.001 * (0.5 * (1 + np.cos(np.pi * e / 30))):.6f}")
        log.append(f"saved runs/centerpoint_v3/ckpt_{epoch}.pth")
    (ck / "train.log").write_text("\n".join(log) + "\n")
    for epoch in range(5, 31, 5):
        splits = ["day", "night"] if epoch == 20 else ["day", "night", "rain"]
        _run_py(root, "eval.py", "--ckpt", f"runs/centerpoint_v3/ckpt_{epoch}.pth", "--splits", *splits)
    (root / "eval" / "20" / "eval.log").write_text(
        "epoch 20 day    done\nepoch 20 night  done\nepoch 20 rain   RuntimeError: CUDA out of memory. "
        "Tried to allocate 1.20 GiB (GPU 0; 23.65 GiB total capacity)\n")
    _clean_pycache(root)
    return root


def loc_bench(dest: Path) -> Path:
    root = dest / "loc_bench"
    _write(root / ".gitignore", "__pycache__/\nresults/\n")
    _write(root / "README.md", '''
        # loc-bench

        Localization benchmark. `python bench.py` runs the estimator on every sequence in `sequences/` and writes
        `sequences/<seq>/estimate.txt` next to `groundtruth.txt` (both TUM format: `t x y z qx qy qz qw`).
        `pytest tests` then checks ATE < 0.15 m and RPE < 0.05 m per sequence. CI runs both on every PR.
        ''')
    _write(root / "requirements.txt", "numpy\npytest\n")
    _write(root / ".github" / "workflows" / "loc-bench.yml", '''
        name: loc-bench
        on:
          pull_request:
          push:
            branches: [main]
        jobs:
          bench:
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with: {python-version: "3.11"}
              - run: pip install -r requirements.txt
              - run: python bench.py
              - run: pytest tests -q --junitxml=results/junit.xml
              - uses: actions/upload-artifact@v4
                if: always()
                with: {name: loc-bench, path: "sequences/*/estimate.txt\\nresults/"}
        ''')
    _write(root / "loc" / "__init__.py", "")
    _write(root / "loc" / "tum.py", '''
        import numpy as np

        def read_tum(path) -> np.ndarray:
            """-> (n, 8): t x y z qx qy qz qw"""
            return np.loadtxt(path, comments="#", ndmin=2)

        def write_tum(path, t, x, y, yaw) -> None:
            z = np.zeros_like(x)
            rows = np.column_stack([t, x, y, z, z, z, np.sin(yaw / 2), np.cos(yaw / 2)])
            np.savetxt(path, rows, fmt=["%.3f"] + ["%.5f"] * 7, header="timestamp tx ty tz qx qy qz qw")
        ''')
    _write(root / "loc" / "estimator.py", '''
        """Wheel odometry dead-reckoning, corrected by scan-match poses (complementary filter)."""
        import numpy as np

        GAIN = 0.12  # weight of a scan-match correction

        def run(odom: np.ndarray, scans: np.ndarray, out_t: np.ndarray):
            """odom: t, v, w (20 Hz). scans: t, x, y, yaw (2 Hz). Returns x, y, yaw at out_t."""
            x = y = yaw = 0.0
            si, xs, ys, yaws, oi = 0, [], [], [], 0
            for k in range(len(odom) - 1):
                t, v, w = odom[k]
                dt = odom[k + 1, 0] - t
                x += v * np.cos(yaw) * dt
                y += v * np.sin(yaw) * dt
                yaw += w * dt
                while si < len(scans) and scans[si, 0] <= odom[k + 1, 0] + 1e-9:
                    _, sx, sy, syaw = scans[si]
                    x += GAIN * (sx - x)
                    y += GAIN * (sy - y)
                    yaw += GAIN * np.arctan2(np.sin(syaw - yaw), np.cos(syaw - yaw))
                    si += 1
                while oi < len(out_t) and out_t[oi] <= odom[k + 1, 0] + 1e-9:
                    xs.append(x); ys.append(y); yaws.append(yaw); oi += 1
            while oi < len(out_t):
                xs.append(x); ys.append(y); yaws.append(yaw); oi += 1
            return np.array(xs), np.array(ys), np.array(yaws)
        ''')
    _write(root / "loc" / "metrics.py", '''
        """ATE (after rigid 2D alignment) and RPE (1 s segments), both RMSE in metres."""
        import numpy as np

        def _align(gt: np.ndarray, est: np.ndarray) -> np.ndarray:
            mg, me = gt.mean(0), est.mean(0)
            u, _, vt = np.linalg.svd((est - me).T @ (gt - mg))
            r = (u @ vt).T
            if np.linalg.det(r) < 0:
                vt[-1] *= -1
                r = (u @ vt).T
            return (est - me) @ r.T + mg

        def ate_rmse(gt, est) -> float:
            g, e = gt[:, 1:3], _align(gt[:, 1:3], est[:, 1:3])
            return float(np.sqrt(np.mean(np.sum((g - e) ** 2, axis=1))))

        def rpe_rmse(gt, est, delta_s: float = 1.0) -> float:
            dt = np.median(np.diff(gt[:, 0]))
            k = max(1, int(round(delta_s / dt)))
            dg = gt[k:, 1:3] - gt[:-k, 1:3]
            de = est[k:, 1:3] - est[:-k, 1:3]
            return float(np.sqrt(np.mean(np.sum((dg - de) ** 2, axis=1))))
        ''')
    _write(root / "bench.py", '''
        """Run the estimator on every sequence; write sequences/<seq>/estimate.txt and print ATE/RPE."""
        from pathlib import Path
        import numpy as np
        from loc import estimator
        from loc.metrics import ate_rmse, rpe_rmse
        from loc.tum import read_tum, write_tum

        SEQUENCES = Path(__file__).parent / "sequences"

        def run_sequence(seq: Path) -> tuple[float, float]:
            gt = read_tum(seq / "groundtruth.txt")
            odom = np.loadtxt(seq / "odometry.csv", delimiter=",", skiprows=1)
            scans = np.loadtxt(seq / "scan_match.csv", delimiter=",", skiprows=1)
            x, y, yaw = estimator.run(odom, scans, gt[:, 0])
            write_tum(seq / "estimate.txt", gt[:, 0], x, y, yaw)
            est = read_tum(seq / "estimate.txt")
            return ate_rmse(gt, est), rpe_rmse(gt, est)

        if __name__ == "__main__":
            print(f"{'sequence':16s} {'ATE (m)':>8s} {'RPE (m)':>8s}")
            for seq in sorted(p for p in SEQUENCES.iterdir() if p.is_dir()):
                ate, rpe = run_sequence(seq)
                print(f"{seq.name:16s} {ate:8.3f} {rpe:8.3f}")
        ''')
    _write(root / "tests" / "test_bench.py", '''
        from pathlib import Path
        import pytest
        from loc.metrics import ate_rmse, rpe_rmse
        from loc.tum import read_tum

        SEQ_DIR = Path(__file__).parent.parent / "sequences"
        SEQUENCES = sorted(p.name for p in SEQ_DIR.iterdir() if p.is_dir())
        ATE_MAX_M = 0.15
        RPE_MAX_M = 0.05

        def _load(seq):
            return read_tum(SEQ_DIR / seq / "groundtruth.txt"), read_tum(SEQ_DIR / seq / "estimate.txt")

        @pytest.mark.parametrize("seq", SEQUENCES)
        def test_ate(seq):
            gt, est = _load(seq)
            assert ate_rmse(gt, est) < ATE_MAX_M

        @pytest.mark.parametrize("seq", SEQUENCES)
        def test_rpe(seq):
            gt, est = _load(seq)
            assert rpe_rmse(gt, est) < RPE_MAX_M
        ''')
    _write(root / "conftest.py", "")  # repo root on sys.path for `loc`
    # sequences: (seed, speed m/s, yaw-rate fn, scan noise m, scan outlier rate)
    seqs = {"warehouse_loop": (1, 1.2, lambda t: 0.2 * np.sin(t / 5), 0.03, 0.0),
            "corridor_long": (2, 1.5, lambda t: 0.02 * np.sin(t / 3), 0.05, 0.0),
            "ramp_up": (3, 0.8, lambda t: 0.12 * np.cos(t / 4), 0.04, 0.02),
            "yard_figure8": (4, 1.6, lambda t: 0.45 * np.sin(t / 6), 0.09, 0.08)}
    for name, (seed, speed, wfn, noise, outliers) in seqs.items():
        rng = np.random.default_rng(seed)
        seq = root / "sequences" / name
        seq.mkdir(parents=True)
        t = np.round(np.arange(0, 30.0001, 0.05), 3)
        w = wfn(t)
        v = speed + 0.1 * np.sin(t / 2)
        yaw = np.concatenate([[0], np.cumsum(w[:-1] * 0.05)])
        x = np.concatenate([[0], np.cumsum(v[:-1] * np.cos(yaw[:-1]) * 0.05)])
        y = np.concatenate([[0], np.cumsum(v[:-1] * np.sin(yaw[:-1]) * 0.05)])
        gi = np.arange(0, len(t), 2)  # groundtruth at 10 Hz
        gz = np.zeros(len(gi))
        np.savetxt(seq / "groundtruth.txt", np.column_stack([t[gi], x[gi], y[gi], gz, gz, gz, np.sin(yaw[gi] / 2), np.cos(yaw[gi] / 2)]),
                   fmt=["%.3f"] + ["%.5f"] * 7, header="timestamp tx ty tz qx qy qz qw")
        vo = v * 1.02 + rng.normal(0, 0.03, len(t))  # wheel scale error
        wo = w + 0.01 + rng.normal(0, 0.01, len(t))  # gyro bias
        np.savetxt(seq / "odometry.csv", np.column_stack([t, vo, wo]), fmt=["%.3f", "%.4f", "%.5f"], delimiter=",",
                   header="t,v_mps,w_radps", comments="")
        si = np.arange(10, len(t), 10)  # scan match at 2 Hz
        sx, sy = x[si] + rng.normal(0, noise, len(si)), y[si] + rng.normal(0, noise, len(si))
        bad = rng.random(len(si)) < outliers
        sx[bad] += rng.normal(0, 0.8, bad.sum())
        np.savetxt(seq / "scan_match.csv", np.column_stack([t[si], sx, sy, yaw[si] + rng.normal(0, 0.01, len(si))]),
                   fmt=["%.3f", "%.4f", "%.4f", "%.5f"], delimiter=",", header="t,x,y,yaw", comments="")
    _run_py(root, "bench.py")
    _clean_pycache(root)
    return root


def _diag(t, statuses) -> dict:
    return {"header": _hdr(t, ""), "status": [
        {"level": lvl, "name": name, "message": msg, "hardware_id": hw, "values": [{"key": k, "value": str(v)} for k, v in vals.items()]}
        for lvl, name, msg, hw, vals in statuses]}


def field_mcap(dest: Path) -> Path:
    root = dest / "field_mcap"
    _write(root / "README.md", '''
        # fleet-logs

        Shift recordings from the warehouse AMRs. The on-robot recorder (`scripts/record_shift.sh`) writes one mcap
        per shift to `logs/<robot>/<date>.mcap`; the nightly sync copies them here.

        | Topic | Type | Rate | Notes |
        |---|---|---|---|
        | `/odom` | nav_msgs/Odometry | 1 Hz (throttled) | wheel odometry |
        | `/localization/pose` | geometry_msgs/PoseWithCovarianceStamped | 1 Hz (throttled) | map-frame localizer output |
        | `/gps/fix` | sensor_msgs/NavSatFix | 1 Hz | outdoor yard only (amr-03) |
        | `/diagnostics` | diagnostic_msgs/DiagnosticArray | 0.2 Hz | localization, autonomy mode, battery |
        | `/teleop/takeover` | acme_fleet_msgs/Takeover | on event | operator e-stop / takeover |

        No ground truth is recorded.
        ''')
    _write(root / "fleet.yaml", '''
        site: warehouse-a
        robots:
          amr-01: {zone: aisles-north, sensors: [lidar, wheel_odom, imu]}
          amr-02: {zone: aisles-south, sensors: [lidar, wheel_odom, imu]}
          amr-03: {zone: yard, sensors: [lidar, wheel_odom, imu, gnss]}
        ''')
    _write(root / "scripts" / "record_shift.sh", '''
        #!/usr/bin/env bash
        # Started by systemd at shift start on each robot; stopped at shift end.
        set -euo pipefail
        robot="$(hostname)"
        out="/data/logs/${robot}/$(date -u +%F)"
        ros2 run topic_tools throttle messages /odom 1.0 /odom_throttled &
        ros2 run topic_tools throttle messages /localization/pose 1.0 /localization/pose_throttled &
        exec ros2 bag record -s mcap -o "$out" \\
          /odom_throttled:=/odom /localization/pose_throttled:=/localization/pose \\
          /gps/fix /diagnostics /teleop/takeover
        ''')
    logs = [("amr-01", (2026, 9, 21)), ("amr-01", (2026, 9, 22)), ("amr-01", (2026, 9, 24)),
            ("amr-02", (2026, 9, 21)), ("amr-02", (2026, 9, 23)),
            ("amr-03", (2026, 9, 22)), ("amr-03", (2026, 9, 24))]
    for i, (robot, day) in enumerate(logs):
        rng = np.random.default_rng(1000 + i)
        yard = robot == "amr-03"
        v2_localizer = day >= (2026, 9, 23)  # localizer 2.3 rollout adds match_score to the pose message
        t0 = _ns(*day, 6, 0, 0) + int(rng.integers(0, 600)) * 1_000_000_000
        n = 300
        # ground-truth path: back and forth along an aisle loop (not recorded)
        s = np.cumsum(np.clip(rng.normal(1.0, 0.2, n), 0, 1.6))
        gx, gy = 20 * np.sin(s / 20), 8 * np.sin(s / 40)
        gyaw = np.arctan2(np.gradient(gy), np.gradient(gx))
        # odometry drifts; localization has a slow error that snaps back on relocalization
        ox = np.cumsum(np.gradient(gx) * 1.015 + rng.normal(0, 0.01, n))
        oy = np.cumsum(np.gradient(gy) * 1.015 + rng.normal(0, 0.01, n))
        err = np.zeros((n, 2))
        relocs = sorted(rng.choice(np.arange(40, n - 10), size=int(rng.integers(1, 4)), replace=False))
        for k in range(1, n):
            err[k] = err[k - 1] + rng.normal(0, 0.03 if not yard else 0.05, 2)
            if k in relocs:
                err[k] = rng.normal(0, 0.03, 2)
        # takeovers and the autonomy mode they cause
        mode = np.array(["AUTO"] * n, dtype=object)
        takeovers = sorted(rng.choice(np.arange(20, n - 40), size=int(rng.integers(0, 4)), replace=False))
        for k in takeovers:
            mode[k:k + int(rng.integers(15, 60))] = "MANUAL"
        mode[:5] = "IDLE"
        recs = []
        for k in range(n):
            t = t0 + k * 1_000_000_000
            recs.append(("/odom", "nav_msgs/msg/Odometry", t + 3_000_000, {
                "header": _hdr(t, "odom"), "child_frame_id": "base_link",
                "pose": {"pose": {"position": {"x": _r(ox[k]), "y": _r(oy[k]), "z": 0.0}, "orientation": _quat_z(gyaw[k])}},
                "twist": {"twist": {"linear": {"x": _r(np.hypot(np.gradient(gx)[k], np.gradient(gy)[k])), "y": 0.0, "z": 0.0},
                                    "angular": {"x": 0.0, "y": 0.0, "z": _r(np.gradient(gyaw)[k], 4)}}}}))
            sd = 0.02 + float(np.hypot(*err[k])) * 0.1
            pose = {"header": _hdr(t, "map"), "pose": {
                "pose": {"position": {"x": _r(gx[k] + err[k, 0]), "y": _r(gy[k] + err[k, 1]), "z": 0.0}, "orientation": _quat_z(gyaw[k])},
                "covariance": [_r(sd ** 2, 5) if j in (0, 7) else (_r(0.0004, 5) if j == 35 else 0.0) for j in range(36)]}}
            if v2_localizer:
                pose["match_score"] = _r(np.clip(0.95 - 0.4 * np.hypot(*err[k]) + rng.normal(0, 0.02), 0, 1))
            recs.append(("/localization/pose", "geometry_msgs/msg/PoseWithCovarianceStamped", t + 9_000_000, pose))
            if yard and 100 <= k < 250:  # outside: GNSS has a fix
                recs.append(("/gps/fix", "sensor_msgs/msg/NavSatFix", t + 15_000_000, {
                    "header": _hdr(t, "gps_link"), "status": {"status": 0 if rng.random() > 0.1 else -1, "service": 1},
                    "latitude": _r(47.60621 + gy[k] / 111_320, 7), "longitude": _r(-122.33207 + gx[k] / 75_000, 7),
                    "altitude": _r(56.2 + rng.normal(0, 0.3), 2),
                    "position_covariance": [0.36, 0.0, 0.0, 0.0, 0.36, 0.0, 0.0, 0.0, 1.44], "position_covariance_type": 2}))
            if k % 5 == 0:
                lvl = 0 if np.hypot(*err[k]) < 0.5 else 1
                recs.append(("/diagnostics", "diagnostic_msgs/msg/DiagnosticArray", t + 20_000_000, _diag(t, [
                    (lvl, "localization", "OK" if lvl == 0 else "pose uncertainty high", robot, {"particles": 800, "map": "warehouse-a_v14"}),
                    (0, "autonomy", mode[k], robot, {"mode": mode[k], "mission": f"pick-{int(t0 // 1e9) % 9973 + k // 60}"}),
                    (0, "battery", "OK", robot, {"percent": _r(92 - k * 0.03, 1)})])))
            if k in takeovers:
                recs.append(("/teleop/takeover", "acme_fleet_msgs/msg/Takeover", t + 500_000_000, {
                    "header": _hdr(t + 500_000_000, "base_link"),
                    "source": str(rng.choice(["pendant", "remote_console"])),
                    "reason": str(rng.choice(["estop", "blocked_aisle", "wrong_turn", "pallet_misaligned"])),
                    "operator_id": f"op-{int(rng.integers(10, 20))}"}))
        recs.append(("/teleop/takeover", "acme_fleet_msgs/msg/Takeover", None, {  # recorder subscribes even when idle
            "header": _hdr(0, "base_link"), "source": "", "reason": "", "operator_id": ""}))
        _write_mcap(root / "logs" / robot / f"{day[0]}-{day[1]:02d}-{day[2]:02d}.mcap", recs)
    return root


# ---- imitation learning (lerobot_act, robomimic_h5) ----

_SO101_JOINTS = ["shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos", "wrist_flex.pos", "wrist_roll.pos", "gripper.pos"]


def _pick_episode(rng, n: int, grasp: bool = True, jerky: bool = False, drop: bool = False):
    """SO-101 pick-and-place joint trajectory (degrees; gripper 0-100). -> state (n,6), action (n,6), ee xy (n,2)."""
    u = np.linspace(0, 1, n)
    cube = rng.uniform([-0.4, 0.3], [0.4, 0.7])
    reach = np.clip(u / 0.35, 0, 1)
    carry = np.clip((u - 0.55) / 0.35, 0, 1)
    ex = (1 - carry) * (reach * cube[0]) + carry * 0.6
    ey = (1 - carry) * (0.2 + reach * (cube[1] - 0.2)) + carry * 0.25
    lift = np.clip((u - 0.45) / 0.1, 0, 1) * (1 - np.clip((u - 0.9) / 0.1, 0, 1))
    grip = np.where((u > 0.4) & (u < 0.92), 8.0, 85.0) if grasp else np.full(n, 85.0) - 10 * np.sin(u * 6)
    if drop:
        grip = np.where(u > 0.7, 85.0, grip)
    state = np.column_stack([np.degrees(np.arctan2(ex, ey)), -40 + 50 * np.hypot(ex, ey) - 20 * lift,
                             60 - 40 * np.hypot(ex, ey) + 15 * lift, 30 + 10 * lift, 5 * np.sin(u * 3), grip])
    state = state + rng.normal(0, 0.15, state.shape)
    action = np.vstack([state[1:], state[-1:]]) + rng.normal(0, 0.3, state.shape)
    if jerky:
        action[:, :5] += rng.normal(0, 6.0, (n, 5))
    if drop:
        cube_xy = np.where((u > 0.4)[:, None] & (u < 0.7)[:, None], np.column_stack([ex, ey]), np.column_stack([np.where(u >= 0.7, ex[int(0.7 * n)], cube[0]), np.where(u >= 0.7, ey[int(0.7 * n)], cube[1])]))
    elif grasp:
        cube_xy = np.where((u > 0.4)[:, None], np.column_stack([ex, ey]), cube)
    else:
        cube_xy = np.tile(cube, (n, 1))
    return state.astype("float32"), action.astype("float32"), np.column_stack([ex, ey]), cube_xy


def _pick_frames(ee, cube_xy, grip, size=64) -> np.ndarray:
    """Top camera: table, bin, cube, arm link and gripper."""
    n = len(ee)
    yy, xx = np.mgrid[0:size, 0:size]
    base = np.zeros((size, size, 3), np.uint8)
    base[:] = (150, 140, 120)
    base[(xx > 46) & (yy > 40) & (yy < 56)] = (60, 60, 160)  # bin
    frames = np.repeat(base[None], n, axis=0)
    to_px = lambda p: (int(32 + p[0] * 36), int(60 - p[1] * 70))
    for k in range(n):
        cx, cy = to_px(cube_xy[k])
        frames[k, max(cy - 3, 0):cy + 3, max(cx - 3, 0):cx + 3] = (200, 30, 30)
        ex, ey = to_px(ee[k])
        for a in np.linspace(0, 1, 24):  # link from the base (32, 62)
            frames[k, int(62 + a * (ey - 62)) % size, int(32 + a * (ex - 32)) % size] = (30, 30, 30)
        r = 1 + int(grip[k] / 40)
        frames[k, max(ey - r, 0):ey + r + 1, max(ex - r, 0):ex + r + 1] = (240, 240, 240)
    return frames


def _lerobot_dataset(root: Path, episodes, task: str, fps: int = 30) -> None:
    """LeRobot v2.1 layout: meta/{info,episodes,tasks,episodes_stats}, data/chunk-000/*.parquet, videos/chunk-000/<key>/*.mp4."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    vkey = "observation.images.top"
    index, ep_lines, stat_lines = 0, [], []
    for e, (state, action, frames) in enumerate(episodes):
        n = len(state)
        tbl = pa.table({
            "action": pa.array([list(map(float, a)) for a in action], type=pa.list_(pa.float32())),
            "observation.state": pa.array([list(map(float, s)) for s in state], type=pa.list_(pa.float32())),
            "timestamp": pa.array(np.arange(n, dtype="float32") / fps, type=pa.float32()),
            "frame_index": pa.array(np.arange(n), type=pa.int64()),
            "episode_index": pa.array(np.full(n, e), type=pa.int64()),
            "index": pa.array(np.arange(index, index + n), type=pa.int64()),
            "task_index": pa.array(np.zeros(n, dtype="int64"), type=pa.int64()),
        })
        path = root / "data" / "chunk-000" / f"episode_{e:06d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(tbl, path)
        _mp4(root / "videos" / "chunk-000" / vkey / f"episode_{e:06d}.mp4", frames, fps)
        ep_lines.append(json.dumps({"episode_index": e, "tasks": [task], "length": n}))
        st = lambda a: {"min": np.round(a.min(0), 3).tolist(), "max": np.round(a.max(0), 3).tolist(),
                        "mean": np.round(a.mean(0), 3).tolist(), "std": np.round(a.std(0), 3).tolist(), "count": [len(a)]}
        stat_lines.append(json.dumps({"episode_index": e, "stats": {"action": st(action), "observation.state": st(state)}}))
        index += n
    feat = lambda: {"dtype": "float32", "shape": [6], "names": _SO101_JOINTS}
    scalar = lambda d: {"dtype": d, "shape": [1], "names": None}
    _json(root / "meta" / "info.json", {
        "codebase_version": "v2.1", "robot_type": "so101_follower", "total_episodes": len(episodes), "total_frames": index,
        "total_tasks": 1, "total_videos": len(episodes), "total_chunks": 1, "chunks_size": 1000, "fps": fps,
        "splits": {"train": f"0:{len(episodes)}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {"action": feat(), "observation.state": feat(),
                     vkey: {"dtype": "video", "shape": [64, 64, 3], "names": ["height", "width", "channels"],
                            "info": {"video.height": 64, "video.width": 64, "video.codec": "h264", "video.pix_fmt": "yuv420p",
                                     "video.is_depth_map": False, "video.fps": fps, "video.channels": 3, "has_audio": False}},
                     "timestamp": scalar("float32"), "frame_index": scalar("int64"), "episode_index": scalar("int64"),
                     "index": scalar("int64"), "task_index": scalar("int64")}})
    (root / "meta" / "episodes.jsonl").write_text("\n".join(ep_lines) + "\n")
    (root / "meta" / "episodes_stats.jsonl").write_text("\n".join(stat_lines) + "\n")
    (root / "meta" / "tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": task}) + "\n")


def _safetensors(path: Path, tensors: dict) -> None:
    header, blobs, off = {}, b"", 0
    for name, arr in tensors.items():
        b = np.ascontiguousarray(arr, dtype="float32").tobytes()
        header[name] = {"dtype": "F32", "shape": list(arr.shape), "data_offsets": [off, off + len(b)]}
        blobs += b
        off += len(b)
    header["__metadata__"] = {"format": "pt"}
    h = json.dumps(header, separators=(",", ":")).encode()
    h += b" " * (-len(h) % 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(h)) + h + blobs)


def lerobot_act(dest: Path) -> Path:
    root = dest / "lerobot_act"
    task = "Pick up the red cube and place it in the blue bin"
    _write(root / "README.md", '''
        # act-pick-cube

        ACT policy for SO-101 pick-and-place, trained with lerobot.

        - `data/`: teleop demos, LeRobot dataset (`acme/so101_pick_cube`); who collected what is in `collection_log.csv`.
        - `scripts/train.sh`: training; checkpoints land in `outputs/train/act_pick_cube/checkpoints/<step>/`.
        - `scripts/eval_real.sh <step>`: rolls a checkpoint on the real arm, 10 trials; episodes are appended to
          `eval_data/` (LeRobot dataset `acme/eval_act_pick_cube`). The operator fills `real_evals/<step>.csv`
          (trial, success, time, notes) by hand during the session.
        ''')
    _write(root / "scripts" / "train.sh", '''
        #!/usr/bin/env bash
        set -euo pipefail
        lerobot-train \\
          --dataset.repo_id=acme/so101_pick_cube --dataset.root=data \\
          --policy.type=act --policy.device=cuda \\
          --output_dir=outputs/train/act_pick_cube --job_name=act_pick_cube \\
          --steps=100000 --save_freq=20000 --batch_size=8 --wandb.enable=false
        ''')
    _write(root / "scripts" / "eval_real.sh", '''
        #!/usr/bin/env bash
        # usage: scripts/eval_real.sh <step>   e.g. 080000
        set -euo pipefail
        step="$1"
        lerobot-record \\
          --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=arm_a \\
          --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \\
          --policy.path="outputs/train/act_pick_cube/checkpoints/${step}/pretrained_model" \\
          --dataset.repo_id=acme/eval_act_pick_cube --dataset.root=eval_data --resume=true \\
          --dataset.single_task="Pick up the red cube and place it in the blue bin" \\
          --dataset.num_episodes=10 --dataset.episode_time_s=20 --dataset.push_to_hub=false
        echo "now fill real_evals/${step}.csv"
        ''')
    # training demos: 3 operators, 2 weeks
    rng = np.random.default_rng(7)
    ops, demos, log = ["op_a", "op_b", "op_c"], [], ["episode_index,operator,date,session"]
    for e in range(18):
        n = int(rng.integers(140, 260))
        kind = {4: "long", 9: "nograsp", 13: "jerky"}.get(e, "ok")
        if kind == "long":
            n = 620
        state, action, ee, cube = _pick_episode(rng, n, grasp=kind != "nograsp", jerky=kind == "jerky")
        demos.append((state, action, _pick_frames(ee, cube, state[:, 5])))
        day = 8 + e * 11 // 18 + (2 if e >= 9 else 0)
        log.append(f"{e},{ops[e % 3] if e < 12 else ops[(e // 2) % 3]},2026-09-{day:02d},s{1 + e // 6}")
    _lerobot_dataset(root / "data", demos, task)
    (root / "collection_log.csv").write_text("\n".join(log) + "\n")
    # checkpoints
    for step in range(20000, 100001, 20000):
        ck = root / "outputs" / "train" / "act_pick_cube" / "checkpoints" / f"{step:06d}"
        _json(ck / "pretrained_model" / "config.json", {"type": "act", "n_obs_steps": 1, "chunk_size": 100, "n_action_steps": 100,
                                                        "dim_model": 512, "n_heads": 8, "vision_backbone": "resnet18",
                                                        "input_features": {"observation.state": {"type": "STATE", "shape": [6]},
                                                                           "observation.images.top": {"type": "VISUAL", "shape": [3, 64, 64]}},
                                                        "output_features": {"action": {"type": "ACTION", "shape": [6]}}})
        _json(ck / "pretrained_model" / "train_config.json", {"dataset": {"repo_id": "acme/so101_pick_cube", "root": "data"},
                                                              "steps": 100000, "save_freq": 20000, "batch_size": 8, "seed": 1000})
        _safetensors(ck / "pretrained_model" / "model.safetensors", {"model.action_head.bias": np.random.default_rng(step).normal(0, 0.02, 6)})
        _json(ck / "training_state" / "training_step.json", {"step": step})
    # real-arm evals: 10 trials per evaluated checkpoint, all appended to eval_data/
    outcomes = {40000: "SFSFFSFSFS", 60000: "SSFSSSFSSF", 80000: "SSSSFSSSSF", 100000: "SFSSFSSFSF"}
    fail_notes = ["missed grasp, gripper closed early", "dropped cube during carry", "timeout, hovered over cube",
                  "knocked cube off table", "placed next to bin", "grasped cube edge, slipped"]
    ok_notes = ["", "", "", "slow approach", "re-grasped once", ""]
    erng, eval_eps = np.random.default_rng(8), []
    (root / "real_evals").mkdir()
    for step, res in outcomes.items():
        rows = [["trial", "success", "time_s", "notes"]]
        for trial, r in enumerate(res, 1):
            ok = r == "S"
            n = int(erng.integers(150, 300)) if ok else int(erng.integers(250, 400))
            mode = "ok" if ok else str(erng.choice(["nograsp", "drop"]))
            state, action, ee, cube = _pick_episode(erng, n, grasp=mode != "nograsp", drop=mode == "drop")
            eval_eps.append((state, action, _pick_frames(ee, cube, state[:, 5])))
            note = str(erng.choice(ok_notes if ok else fail_notes))
            rows.append([trial, "yes" if ok else "no", f"{n / 30 + erng.normal(0.4, 0.2):.1f}", note])
        _csv(root / "real_evals" / f"{step:06d}.csv", rows)
    _lerobot_dataset(root / "eval_data", eval_eps, task)
    return root


def robomimic_h5(dest: Path) -> Path:
    import h5py
    root = dest / "robomimic_h5"
    _write(root / "README.md", '''
        # diffusion-policy-robomimic

        Diffusion policy on robomimic `lift`, `can`, `square` (PH, low-dim). Training writes `ckpts/epoch_<n>.pt`
        (not in git). Rollouts:

        ```
        python rollout.py --ckpt ckpts/epoch_300.pt
        ```

        writes `rollouts/epoch_<n>.hdf5`: 50 rollouts per task, robomimic layout
        (`data/demo_<i>/{obs,actions,rewards,dones}`, attrs `success`, `task`).
        ''')
    _write(root / ".gitignore", "ckpts/\n")
    _write(root / "configs" / "dp_lowdim.yaml", '''
        policy: diffusion_unet_lowdim
        horizon: 16
        n_action_steps: 8
        n_obs_steps: 2
        num_inference_steps: 100
        tasks: [lift, can, square]
        train: {num_epochs: 500, checkpoint_every: 100, lr: 1.0e-4, batch_size: 256}
        rollout: {n_rollouts_per_task: 50, horizon: {lift: 30, can: 45, square: 60}, control_hz: 10, seed: 100000}
        ''')
    _write(root / "rollout.py", '''
        """Roll out a diffusion-policy checkpoint on robomimic tasks. Writes rollouts/epoch_<n>.hdf5."""
        import argparse, json, re
        from pathlib import Path
        import h5py, numpy as np, yaml

        def main() -> None:
            ap = argparse.ArgumentParser()
            ap.add_argument("--ckpt", required=True)
            ap.add_argument("--config", default="configs/dp_lowdim.yaml")
            a = ap.parse_args()
            import torch  # heavy deps only when actually rolling out
            import robomimic.utils.env_utils as EnvUtils
            from diffusion_policy.policy import load_policy
            cfg = yaml.safe_load(open(a.config))
            epoch = int(re.search(r"epoch_(\\d+)\\.pt$", a.ckpt).group(1))
            policy = load_policy(torch.load(a.ckpt, map_location="cuda"))
            out = Path("rollouts") / f"epoch_{epoch}.hdf5"
            out.parent.mkdir(exist_ok=True)
            with h5py.File(out, "w") as f:
                data = f.create_group("data")
                i = 0
                for task in cfg["tasks"]:
                    env = EnvUtils.create_env_from_metadata(env_meta=json.load(open(f"configs/env_{task}.json")))
                    for r in range(cfg["rollout"]["n_rollouts_per_task"]):
                        traj = policy.rollout(env, horizon=cfg["rollout"]["horizon"][task], seed=cfg["rollout"]["seed"] + r)
                        g = data.create_group(f"demo_{i}")
                        for k, v in traj["obs"].items():
                            g.create_dataset(f"obs/{k}", data=v)
                        for k in ("actions", "rewards", "dones"):
                            g.create_dataset(k, data=traj[k])
                        g.attrs.update(success=bool(traj["success"]), task=task, num_samples=len(traj["actions"]), seed=cfg["rollout"]["seed"] + r)
                        i += 1
                data.attrs.update(total=i, epoch=epoch, ckpt=a.ckpt)

        if __name__ == "__main__":
            main()
        ''')
    rates = {100: {"lift": 0.84, "can": 0.52, "square": 0.18}, 200: {"lift": 0.98, "can": 0.80, "square": 0.42},
             300: {"lift": 1.0, "can": 0.90, "square": 0.58}}
    horizon = {"lift": 30, "can": 45, "square": 60}  # 10 Hz control
    obj_dim = {"lift": 10, "can": 10, "square": 10}
    for epoch, rate in rates.items():
        rng = np.random.default_rng(epoch)
        path = root / "rollouts" / f"epoch_{epoch}.hdf5"
        path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(path, "w", libver="latest") as f:
            data = f.create_group("data")
            i = 0
            for task in ("lift", "can", "square"):
                succ = rng.random(50) < rate[task]
                for r in range(50):
                    n = int(rng.integers(horizon[task] // 3, horizon[task] * 2 // 3)) if succ[r] else horizon[task]
                    u = np.linspace(0, 1, n)[:, None]
                    eef = (np.array([0.0, 0.0, 1.0]) + u * rng.normal(0, 0.1, 3) + rng.normal(0, 0.002, (n, 3))).astype("float32")
                    grip = np.column_stack([0.04 - 0.035 * (u[:, 0] > 0.4), -0.04 + 0.035 * (u[:, 0] > 0.4)]).astype("float32")
                    obj = (rng.normal(0, 0.05, obj_dim[task]) + u * 0.02).astype("float32")
                    act = np.clip(np.diff(np.vstack([eef, eef[-1:]]), axis=0) * 20 + rng.normal(0, 0.05, (n, 3)), -1, 1)
                    act = np.column_stack([act, np.zeros((n, 3)), np.where(u[:, 0] > 0.4, 1.0, -1.0)]).astype("float32")
                    rew = np.zeros(n, "float64")
                    dones = np.zeros(n, "int64")
                    if succ[r]:
                        rew[-1], dones[-1] = 1.0, 1
                    g = data.create_group(f"demo_{i}")
                    for k, v in {"robot0_eef_pos": eef, "robot0_gripper_qpos": grip, "object": obj}.items():
                        g.create_dataset(f"obs/{k}", data=v)
                    g.create_dataset("actions", data=act)
                    g.create_dataset("rewards", data=rew)
                    g.create_dataset("dones", data=dones)
                    g.attrs["success"] = bool(succ[r])
                    g.attrs["task"] = task
                    g.attrs["num_samples"] = n
                    g.attrs["seed"] = 100000 + r
                    i += 1
            data.attrs["total"] = i
            data.attrs["epoch"] = epoch
            data.attrs["ckpt"] = f"ckpts/epoch_{epoch}.pt"
    return root


# ---- testing (behavior_ci, hil_bench) ----

def behavior_ci(dest: Path) -> Path:
    import yaml
    root = dest / "behavior_ci"
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # behavior-sim

        Nightly behavior regression: ~400 scenarios in `scenarios/<family>/<scenario_id>.yaml`, run by `simtest`.

        ```
        python -m simtest run scenarios/ --out results/
        ```

        Writes `results/<scenario_id>.json` (pass, min_ttc_s, max_decel, collisions, route_completion),
        `results/junit.xml` and `results/summary.json`. Scenario ids never change once added.

        CI: `.github/workflows/nightly.yml` (every night on main) and `.github/workflows/release.yml`
        (release candidate tags `rc-*`).
        ''')
    _write(root / "requirements.txt", "numpy\npyyaml\n")
    for wf, trigger in (("nightly", 'schedule:\n    - cron: "0 3 * * *"\n  workflow_dispatch:'),
                        ("release", 'push:\n    tags: ["rc-*"]')):
        _write(root / ".github" / "workflows" / f"{wf}.yml", f'''
            name: {wf}
            on:
              {trigger}
            jobs:
              simtest:
                runs-on: [self-hosted, sim]
                timeout-minutes: 120
                steps:
                  - uses: actions/checkout@v4
                  - uses: actions/setup-python@v5
                    with: {{python-version: "3.11"}}
                  - run: pip install -r requirements.txt
                  - run: python -m simtest run scenarios/ --out results/
                  - uses: actions/upload-artifact@v4
                    if: always()
                    with: {{name: simtest-{wf}-${{{{ github.run_id }}}}, path: results/}}
                  - uses: mikepenz/action-junit-report@v4
                    if: always()
                    with: {{report_paths: results/junit.xml}}
            ''')
    _write(root / "simtest" / "__init__.py", '"""Behavior scenario runner."""\n')
    _write(root / "simtest" / "__main__.py", '''
        import argparse
        from pathlib import Path
        from simtest.runner import run_all

        ap = argparse.ArgumentParser(prog="simtest")
        sub = ap.add_subparsers(dest="cmd", required=True)
        r = sub.add_parser("run")
        r.add_argument("scenarios", type=Path)
        r.add_argument("--out", type=Path, default=Path("results"))
        r.add_argument("--filter", default="", help="substring of scenario ids to run")
        a = ap.parse_args()
        raise SystemExit(run_all(a.scenarios, a.out, a.filter))
        ''')
    _write(root / "simtest" / "runner.py", '''
        """Longitudinal + lateral toy dynamics: ego follows a route while one actor does the scenario's maneuver."""
        import json, os, time
        from datetime import datetime, timezone
        from pathlib import Path
        from xml.sax.saxutils import escape
        import numpy as np
        import yaml

        DT, MAX_DECEL = 0.1, 8.0
        PASS = {"min_ttc_s": 1.5, "max_decel": 6.0, "route_completion": 0.95}

        def simulate(sc: dict) -> dict:
            p = sc["params"]
            rng = np.random.default_rng(sc["seed"])
            ego_v, ego_x, gap = p["ego_speed"], 0.0, p["gap_m"]
            actor_x, actor_v = gap, p["actor_speed"]
            min_ttc, max_decel, collisions, steps = 99.0, 0.0, 0, int(sc["duration_s"] / DT)
            for k in range(steps):
                t = k * DT
                if p.get("event_t", 3.0) < t < p.get("event_t", 3.0) + 2.0:  # actor brakes for 2 s, then holds speed
                    actor_v = max(0.0, actor_v - p.get("actor_brake", 0.0) * DT)
                rel_v = ego_v - actor_v
                dist = actor_x - ego_x - 4.5
                ttc = dist / rel_v if rel_v > 0.1 else 99.0
                min_ttc = min(min_ttc, ttc)
                want = 0.0 if ttc > p["planner_ttc"] else min(MAX_DECEL, rel_v ** 2 / max(2 * (dist - 6.0), 0.5))
                want += abs(rng.normal(0, 0.15))
                max_decel = max(max_decel, want)
                ego_v = max(0.0, ego_v - want * DT)
                ego_x += ego_v * DT
                actor_x += actor_v * DT
                if dist <= 0:
                    collisions += 1
                    break
            route = min(1.0, ego_x / max(p["route_m"], 1.0))
            return {"min_ttc_s": round(min(min_ttc, 99.0), 3), "max_decel": round(max_decel, 3),
                    "collisions": collisions, "route_completion": round(route, 4)}

        def run_all(scen_dir: Path, out: Path, filt: str = "") -> int:
            out.mkdir(parents=True, exist_ok=True)
            started = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cases, failures = [], 0
            for f in sorted(scen_dir.rglob("*.yaml")):
                sc = yaml.safe_load(f.read_text())
                if filt not in sc["id"]:
                    continue
                t0 = time.perf_counter()
                m = simulate(sc)
                ok = (m["collisions"] == 0 and m["min_ttc_s"] >= PASS["min_ttc_s"] and m["max_decel"] <= PASS["max_decel"]
                      and m["route_completion"] >= PASS["route_completion"])
                res = {"scenario_id": sc["id"], "family": sc["family"], "pass": ok, **m}
                (out / f"{sc['id']}.json").write_text(json.dumps(res, indent=2) + "\\n")
                cases.append((sc, res, time.perf_counter() - t0))
                failures += not ok
            lines = [f'<?xml version="1.0" encoding="utf-8"?>',
                     f'<testsuites><testsuite name="simtest" tests="{len(cases)}" failures="{failures}" errors="0" timestamp="{started}">']
            for sc, res, dt in cases:
                lines.append(f'<testcase classname="simtest.{sc["family"]}" name="{sc["id"]}" time="{dt:.3f}">')
                if not res["pass"]:
                    why = ", ".join(f"{k}={res[k]}" for k in ("collisions", "min_ttc_s", "max_decel", "route_completion"))
                    lines.append(f'<failure message="{escape(why)}">{escape(json.dumps(res))}</failure>')
                lines.append("</testcase>")
            lines.append("</testsuite></testsuites>")
            (out / "junit.xml").write_text("\\n".join(lines) + "\\n")
            (out / "summary.json").write_text(json.dumps({
                "started_at": started, "commit": os.environ.get("GITHUB_SHA"), "ref": os.environ.get("GITHUB_REF_NAME"),
                "scenarios": len(cases), "passed": len(cases) - failures, "failed": failures}, indent=2) + "\\n")
            print(f"{len(cases) - failures}/{len(cases)} passed")
            return 1 if failures else 0
        ''')
    families = {"cut_in": 64, "lead_brake": 58, "ped_crossing": 52, "unprotected_left": 47, "merge": 50,
                "cyclist_overtake": 41, "stop_and_go": 55, "occluded_ped": 45}  # 412 total
    rng = np.random.default_rng(2026)
    for fam, count in families.items():
        for i in range(1, count + 1):
            sid = f"{fam}_{i:03d}"
            hard = rng.random() < 0.05
            ego = float(np.round(rng.uniform(8, 25), 1))
            actor = float(np.round(ego * rng.uniform(0.75, 1.0), 1))
            sc = {"id": sid, "family": fam, "seed": int(rng.integers(1, 10_000)), "duration_s": 15.0,
                  "map": str(rng.choice(["town_grid_v3", "suburb_loop_v2", "highway_ring_v1"])),
                  "params": {"ego_speed": ego, "actor_speed": actor,
                             "gap_m": float(np.round(rng.uniform(35, 70) if not hard else rng.uniform(9, 14), 1)),
                             "actor_brake": float(np.round(rng.uniform(0, 3) if not hard else rng.uniform(3, 5), 1)),
                             "event_t": float(np.round(rng.uniform(1, 5), 1)),
                             "planner_ttc": 5.0, "route_m": float(np.round(actor * 15 * 0.55, 1))}}
            _write(root / "scenarios" / fam / f"{sid}.yaml", yaml.safe_dump(sc, sort_keys=False))
    subprocess.run([sys.executable, "-m", "simtest", "run", "scenarios/", "--out", "results/"], cwd=root,
                   stdout=subprocess.DEVNULL, env={**os.environ, "GITHUB_SHA": "4f1c9e2a7b3d5e6f8091a2b3c4d5e6f708192a3b",
                                                    "GITHUB_REF_NAME": "main"})
    # last night's CI run: fixed timestamps instead of this machine's clock
    import re
    junit = (root / "results" / "junit.xml").read_text()
    junit = re.sub(r'timestamp="[^"]+"', 'timestamp="2026-09-30T03:00:12+00:00"', junit)
    junit = re.sub(r'time="[^"]+"', lambda m, c=iter(range(10**6)): f'time="{0.004 + (next(c) % 7) * 0.001:.3f}"', junit)
    (root / "results" / "junit.xml").write_text(junit)
    summ = json.loads((root / "results" / "summary.json").read_text())
    summ["started_at"] = "2026-09-30T03:00:12+00:00"
    _json(root / "results" / "summary.json", summ)
    _clean_pycache(root)
    return root


def hil_bench(dest: Path) -> Path:
    root = dest / "hil_bench"
    _write(root / ".gitignore", "__pycache__/\n.venv/\n")
    _write(root / "README.md", '''
        # motor-hil

        Hardware-in-the-loop tests for the MC4 motor controller. Jenkins (bench PC `hil-bench-01`) runs

        ```
        pytest tests/hil -m hil --junitxml=out/junit.xml
        ```

        against the controller on `/dev/ttyACM0`. Each test logs its current/velocity trace to `out/<test>/trace.csv`;
        the session reads the device identity (serial, firmware) over serial into `out/device.json`.
        `--hil-backend=sim` runs against the plant model instead of hardware (no bench needed).
        ''')
    _write(root / "Jenkinsfile", '''
        pipeline {
          agent { label 'hil-bench-01' }
          options { timeout(time: 30, unit: 'MINUTES') }
          stages {
            stage('Setup') { steps { sh 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt' } }
            stage('HIL') { steps { sh 'rm -rf out && .venv/bin/pytest tests/hil -m hil --junitxml=out/junit.xml' } }
          }
          post {
            always {
              junit 'out/junit.xml'
              archiveArtifacts artifacts: 'out/**', fingerprint: false
            }
          }
        }
        ''')
    _write(root / "requirements.txt", "pytest\npyserial\nnumpy\n")
    _write(root / "pytest.ini", '''
        [pytest]
        markers =
            hil: needs the motor controller bench (or --hil-backend=sim)
        ''')
    _write(root / "bench" / "__init__.py", "")
    _write(root / "bench" / "link.py", '''
        """Serial protocol for the MC4 controller: line-based ASCII commands."""
        import json

        class SerialController:
            def __init__(self, port: str, baud: int = 921600):
                import serial  # pyserial
                self._s = serial.Serial(port, baud, timeout=1.0)

            def _cmd(self, line: str) -> str:
                self._s.write((line + "\\n").encode())
                return self._s.readline().decode().strip()

            def identify(self) -> dict:
                return json.loads(self._cmd("ID?"))

            def set_velocity(self, rpm: float) -> None:
                self._cmd(f"VEL {rpm:.1f}")

            def set_current_limit(self, amps: float) -> None:
                self._cmd(f"ILIM {amps:.2f}")

            def lock_rotor(self, locked: bool) -> None:
                self._cmd(f"BRAKE {int(locked)}")  # bench brake fixture

            def sample(self) -> tuple[float, float, float, int]:
                """-> (t_s, current_a, velocity_rpm, fault_code)"""
                t, i, v, f = self._cmd("SAMPLE?").split(",")
                return float(t), float(i), float(v), int(f)

            def close(self) -> None:
                self.set_velocity(0)
                self._s.close()
        ''')
    _write(root / "bench" / "sim.py", '''
        """Plant model of the MC4 + bench motor, same interface as SerialController."""
        import numpy as np

        class SimController:
            DT = 0.002
            def __init__(self, firmware: str = "2.7.1", seed: int = 0):
                self.fw, self.t, self.v, self.i, self.cmd, self.ilim, self.locked = firmware, 0.0, 0.0, 0.0, 0.0, 6.0, False
                self.rng = np.random.default_rng(seed)
                self.stall_t = None

            def identify(self) -> dict:
                return {"model": "MC4", "serial": "MC4-SIM", "firmware": self.fw, "hw_rev": "C", "bootloader": "1.3.0"}

            def set_velocity(self, rpm): self.cmd = rpm
            def set_current_limit(self, amps): self.ilim = amps
            def lock_rotor(self, locked): self.locked, self.stall_t = locked, None

            def sample(self):
                kp = 0.012 if self.fw >= "2.7" else 0.016  # 2.7 retuned the velocity loop (softer)
                err = self.cmd - self.v
                self.i = float(np.clip(kp * err + 0.00013 * self.v, -self.ilim, self.ilim))
                if not self.locked:
                    self.v += (self.i * 3100 - 0.4 * self.v) * self.DT
                fault = 0
                if self.locked and abs(self.i) >= self.ilim * 0.98:
                    self.stall_t = self.stall_t if self.stall_t is not None else self.t
                    fault = 3 if self.t - self.stall_t > 0.15 else 0
                self.t += self.DT
                return (round(self.t, 4), round(self.i + self.rng.normal(0, 0.01), 4),
                        round(self.v + self.rng.normal(0, 2.0), 2), fault)

            def close(self): pass
        ''')
    _write(root / "tests" / "hil" / "conftest.py", '''
        import csv, json
        from pathlib import Path
        import pytest

        OUT = Path("out")

        def pytest_addoption(parser):
            parser.addoption("--hil-port", default="/dev/ttyACM0")
            parser.addoption("--hil-backend", choices=["serial", "sim"], default="serial")

        @pytest.fixture(scope="session")
        def controller(request):
            if request.config.getoption("--hil-backend") == "sim":
                from bench.sim import SimController
                c = SimController()
            else:
                from bench.link import SerialController
                c = SerialController(request.config.getoption("--hil-port"))
            OUT.mkdir(exist_ok=True)
            (OUT / "device.json").write_text(json.dumps(c.identify(), indent=2) + "\\n")
            yield c
            c.close()

        @pytest.fixture
        def trace(request, controller):
            """Call trace(n) to record n samples; written to out/<test>/trace.csv when the test ends."""
            rows = []
            def record(n):
                got = [controller.sample() for _ in range(n)]
                rows.extend(got)
                return got
            yield record
            d = OUT / request.node.name
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "trace.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["t_s", "current_a", "velocity_rpm", "fault"])
                w.writerows(rows)
        ''')
    _write(root / "tests" / "hil" / "test_motor.py", '''
        import pytest

        RISE_TIME_MAX_S = 0.120   # 10-90 % of the step
        OVERSHOOT_MAX = 0.08
        CURRENT_LIMIT_A = 4.0

        def rise_time(samples, target):
            t = [s[0] for s in samples]
            v = [s[2] for s in samples]
            t10 = next(ti for ti, vi in zip(t, v) if vi >= 0.1 * target)
            t90 = next((ti for ti, vi in zip(t, v) if vi >= 0.9 * target), float("inf"))
            return t90 - t10

        @pytest.fixture(autouse=True)
        def _settle(controller):
            controller.lock_rotor(False)
            controller.set_current_limit(6.0)
            controller.set_velocity(0)
            for _ in range(400):
                controller.sample()
            yield
            controller.set_velocity(0)

        @pytest.mark.hil
        @pytest.mark.parametrize("rpm", [500, 1500, 3000], ids=lambda r: f"{r}rpm")
        def test_step_response(controller, trace, rpm):
            controller.set_velocity(rpm)
            s = trace(300)
            assert rise_time(s, rpm) < RISE_TIME_MAX_S
            assert max(x[2] for x in s) < rpm * (1 + OVERSHOOT_MAX)

        @pytest.mark.hil
        def test_current_limit(controller, trace):
            controller.set_current_limit(CURRENT_LIMIT_A)
            controller.set_velocity(3000)
            s = trace(300)
            assert max(abs(x[1]) for x in s) <= CURRENT_LIMIT_A * 1.05

        @pytest.mark.hil
        def test_reverse(controller, trace):
            controller.set_velocity(1000)
            trace(200)
            controller.set_velocity(-1000)
            s = trace(300)
            assert s[-1][2] < -900

        @pytest.mark.hil
        def test_stall_detect(controller, trace):
            controller.lock_rotor(True)
            controller.set_current_limit(3.0)
            controller.set_velocity(1500)
            s = trace(200)
            controller.lock_rotor(False)
            first = next((x[0] for x in s if x[3] == 3), None)
            assert first is not None and first - s[0][0] < 0.2
        ''')
    _write(root / "conftest.py", "")  # repo root on sys.path for `bench`
    # last Jenkins run on the bench (plant model stands in for the hardware when generating the fixture)
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/hil", "-m", "hil",
                    "--hil-backend=sim", "--junitxml=out/junit.xml"], cwd=root, stdout=subprocess.DEVNULL)
    _json(root / "out" / "device.json", {"model": "MC4", "serial": "MC4-00172", "firmware": "2.7.1", "hw_rev": "C",
                                         "bootloader": "1.3.0", "port": "/dev/ttyACM0"})
    import re
    junit = (root / "out" / "junit.xml").read_text()
    junit = re.sub(r'timestamp="[^"]+"', 'timestamp="2026-09-30T22:14:05.118342+00:00"', junit)
    junit = re.sub(r'hostname="[^"]+"', 'hostname="hil-bench-01"', junit)
    junit = re.sub(r"0x[0-9a-f]{6,}", "0x7f3a1c2e4b90", junit)
    junit = re.sub(r' time="[^"]+"', lambda m, c=iter(range(100)): f' time="{[3.412, 0.731, 0.702, 0.744, 0.698, 0.81, 0.512][next(c) % 7]:.3f}"', junit)
    (root / "out" / "junit.xml").write_text(junit)
    _clean_pycache(root)
    return root


# ---- variants of the base fixtures, routing cases ----

_BRIEFS = Path(__file__).resolve().parent.parent / "fixtures" / "briefs"
_CONFIGS = Path(__file__).resolve().parent.parent / "fixtures" / "configs"


def rl_project_with_brief(dest: Path) -> Path:
    """rl_project + the brief approved last week: onboard sections filled, the rest pending."""
    root = _derive(rl_project, dest, "rl_project_with_brief")
    brief = (_BRIEFS / "o2.md").read_text()
    brief = brief.replace("`skilltest-project`", "`acme-robotics`").replace("approved by user 2026-09-28", "approved by user 2026-09-24")
    brief = brief.replace("# Checkpoint evals — SignalFlag brief", "# Checkpoint evals — SignalFlag test brief")
    _write(root / "docs" / "signalflag" / "checkpoint-eval-test-brief.md", brief)
    return root


def pytest_suite_with_brief_plus_sim(dest: Path) -> Path:
    """pytest_suite already integrated (hook + config + finished brief), plus a new closed-loop sim runner."""
    root = _derive(pytest_suite, dest, "pytest_suite_with_brief_plus_sim")
    _write(root / ".gitignore", "__pycache__/\n")
    brief = (_BRIEFS / "pytest.md").read_text().replace("`skilltest-project`", "`acme-robotics`")
    brief = brief.replace("# Planner tests — SignalFlag brief\n", "# Planner tests — SignalFlag test brief\n\nStatus: approved by user 2026-09-25.\n")
    brief = brief.replace("## Verification\n_pending: signalflag-verify_", textwrap.dedent('''\
        ## Verification
        - Full push 2026-09-29 to `planner-ci` (version `9c2e41d`): 4 tests, `clutter` FAIL_BLOCK on Path Ratio and Clearance Margin, others PASSED. No render or query errors.
        - CI: `SIGNALFLAG_UPLOAD=1` set in the PR workflow with the service credential (signalflag-auth).
        - Next: signalflag-iterate for changes.'''))
    _write(root / "docs" / "signalflag" / "planner-test-brief.md", brief)
    cfg = root / ".resim" / "metrics" / "config.resim.yml"
    cfg.parent.mkdir(parents=True)
    shutil.copy(_CONFIGS / "pytest" / ".resim" / "metrics" / "config.resim.yml", cfg)
    _write(root / "pyproject.toml", '''
        [project]
        name = "planner"
        version = "0.1.0"
        dependencies = []

        [project.optional-dependencies]
        dev = ["pytest"]
        signalflag = ["signalflag==1.8.0"]
        ''')
    _write(root / "conftest.py", '''
        """SignalFlag upload for the planner suite. Opt-in: SIGNALFLAG_UPLOAD=1 (needs `pip install -e .[signalflag]`)."""
        import os, subprocess, tempfile
        from pathlib import Path
        import pytest

        ROOT = Path(__file__).resolve().parent
        CFG = ROOT / ".resim" / "metrics"
        ENABLED = os.environ.get("SIGNALFLAG_UPLOAD") == "1"
        _results = {}

        def pytest_addoption(parser):
            g = parser.getgroup("signalflag")
            g.addoption("--sf-branch", default="planner-ci")
            g.addoption("--sf-version", default=None)

        @pytest.fixture
        def record_result(request):
            def record(result):
                _results[request.node.callspec.id] = (result, request.node)
            return record

        def _version() -> str:
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
            dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
            return sha + ("-dirty" if dirty else "")

        def pytest_sessionfinish(session, exitstatus):
            if not ENABLED or not _results:
                return
            from signalflag.sdk.auth import DeviceCodeClient
            from signalflag.sdk.batch import Batch
            from signalflag.sdk.test import Test
            opt = session.config.getoption
            client = DeviceCodeClient()
            cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)  # Test writes emissions files into cwd
                with Batch(client, project_name="acme-robotics", branch=opt("--sf-branch"), version=opt("--sf-version") or _version(),
                           metrics_set_name="Planner Tests", metrics_config_path=str(CFG / "config.resim.yml"),
                           templates_path=str(CFG / "templates")) as batch:
                    for scenario, (r, node) in sorted(_results.items()):
                        ratio, margin = r.path_length_m / r.straight_m, r.min_clearance_m - 0.25
                        with Test(client, batch, name=scenario) as t:
                            t.emit("plan_result", {"scenario": scenario, "path_length_m": r.path_length_m, "straight_m": r.straight_m,
                                                   "min_clearance_m": r.min_clearance_m, "path_ratio": ratio,
                                                   "clearance_margin_m": margin, "passed": ratio < 1.2 and margin > 0}, 0)
                os.chdir(cwd)
                print(f"\\nSignalFlag: https://app.signalflag.ai/projects/{batch.project_id}/batches/{batch.id}")
        ''')
    _write(root / "tests" / "test_planner.py", '''
        import pytest
        from planner.plan import plan

        @pytest.mark.parametrize("scenario", ["open", "one_box", "corridor", "clutter"])
        def test_plan(scenario, record_result):
            r = plan(scenario)
            record_result(r)
            assert r.path_length_m < 1.2 * r.straight_m
            assert r.min_clearance_m > 0.25
        ''')
    _write(root / ".github" / "workflows" / "planner.yml", '''
        name: planner
        on: [pull_request]
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with: {python-version: "3.11"}
              - run: pip install -e .[dev,signalflag]
              - run: pytest -q
                env:
                  SIGNALFLAG_UPLOAD: "1"
                  SIGNALFLAG_CLIENT_ID: ${{ secrets.SIGNALFLAG_CLIENT_ID }}
                  SIGNALFLAG_CLIENT_SECRET: ${{ secrets.SIGNALFLAG_CLIENT_SECRET }}
        ''')
    _write(root / "sim" / "run_suite.py", '''
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
                (out / "result.json").write_text(json.dumps(res, indent=2) + "\\n")
                np.savetxt(out / "trajectory.csv", traj, delimiter=",", header="t_s,x_m,lateral_m", comments="", fmt="%.4f")
                print(scenario, res)
        ''')
    _run_py(root, "sim/run_suite.py", "--seed", "1", "--stamp", "20260930T101500")
    _run_py(root, "sim/run_suite.py", "--seed", "2", "--stamp", "20260930T143000")
    _clean_pycache(root)
    return root


def monorepo(dest: Path) -> Path:
    root = dest / "monorepo"
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # acme-av

        - `perception/`: perception replay harness (ROS 2, docker compose). See perception/README.md.
        - `planning/`: lattice planner + its pytest suite. See planning/README.md.
        ''')
    perc = root / "perception"
    names = ["urban_intersection_01", "roundabout_merge_05", "construction_zone_06"]
    _replay_harness(perc, names, "registry.acme.dev/av/perception:2026.09.1")
    _write(perc / "README.md", '''
        # perception replay

        `docker compose --profile replay up` plays `scenarios/*.mcap` through the stack; outputs land in
        `outputs/<scenario>/output.mcap` (`/perception/detections`, `/perception/tracks`). Image tag in `compose.yaml`.
        ''')
    _replay_outputs(perc, names, (2026, 9, 26, 11, 0, 0))
    plan = root / "planning"
    _write(plan / "README.md", '''
        # planning

        Lattice planner. `cd planning && pytest` (CI runs it on every PR touching planning/).
        ''')
    _write(plan / "pyproject.toml", '''
        [project]
        name = "acme-planning"
        version = "0.4.0"
        dependencies = ["numpy"]

        [project.optional-dependencies]
        test = ["pytest"]
        ''')
    _write(plan / "conftest.py", "")
    _write(plan / "lattice" / "__init__.py", "")
    _write(plan / "lattice" / "planner.py", '''
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
        ''')
    _write(plan / "tests" / "test_planner.py", '''
        import pytest
        from lattice.planner import plan

        @pytest.mark.parametrize("speed,lane", [(10, 1), (10, -1), (25, 1), (30, -1)], ids=["slow-left", "slow-right", "fast-left", "fast-right"])
        def test_lane_change(speed, lane):
            p = plan(speed, target_lane=lane)
            assert p.max_lat_accel < 2.0

        @pytest.mark.parametrize("obstacle_s", [15.0, 30.0, 60.0])
        def test_stop_before_obstacle(obstacle_s):
            p = plan(12.0, obstacle_s=obstacle_s)
            assert p.stop_s is not None and p.stop_s <= obstacle_s - 1.5

        @pytest.mark.parametrize("gap", [20.0, 40.0])
        def test_follow_gap(gap):
            assert plan(15.0, lead_gap_m=gap).min_gap_m > 0
        ''')
    _write(root / ".github" / "workflows" / "planning.yml", '''
        name: planning
        on:
          pull_request:
            paths: ["planning/**"]
        jobs:
          pytest:
            runs-on: ubuntu-latest
            defaults: {run: {working-directory: planning}}
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with: {python-version: "3.11"}
              - run: pip install -e .[test]
              - run: pytest -q
        ''')
    return root


def _ros1_bag(path: Path, conns, msgs) -> None:
    """Minimal ROS1 bag v2.0: one uncompressed chunk, index data, connection + chunk info records.
    conns: [(topic, type, md5, definition)]; msgs: [(conn_id, t_ns, payload)] sorted by time."""
    def field(k, v: bytes):
        b = k.encode() + b"=" + v
        return struct.pack("<i", len(b)) + b
    def record(hdr: dict, data: bytes):
        h = b"".join(field(k, v) for k, v in hdr.items())
        return struct.pack("<i", len(h)) + h + struct.pack("<i", len(data)) + data
    i32 = lambda x: struct.pack("<i", x)
    t64 = lambda t: struct.pack("<II", t // 1_000_000_000, t % 1_000_000_000)
    def conn_rec(cid):
        topic, typ, md5, defn = conns[cid]
        data = b"".join(field(k, v.encode()) for k, v in [("topic", topic), ("type", typ), ("md5sum", md5),
                                                          ("message_definition", defn), ("callerid", "/record_1684"), ("latching", "0")])
        return record({"op": b"\x07", "conn": i32(cid), "topic": topic.encode()}, data)
    chunk_data, index = b"", {c: [] for c in range(len(conns))}
    for c in range(len(conns)):
        chunk_data += conn_rec(c)
    for cid, t, payload in msgs:
        index[cid].append((t, len(chunk_data)))
        chunk_data += record({"op": b"\x02", "conn": i32(cid), "time": t64(t)}, payload)
    chunk = record({"op": b"\x05", "compression": b"none", "size": i32(len(chunk_data))}, chunk_data)
    idx = b"".join(record({"op": b"\x04", "ver": i32(1), "conn": i32(c), "count": i32(len(v))},
                          b"".join(t64(t) + i32(off) for t, off in v)) for c, v in index.items())
    magic, header_len = b"#ROSBAG V2.0\n", 4096
    chunk_pos = len(magic) + header_len
    index_pos = chunk_pos + len(chunk) + len(idx)
    tail = b"".join(conn_rec(c) for c in range(len(conns)))
    tail += record({"op": b"\x06", "ver": i32(1), "chunk_pos": struct.pack("<Q", chunk_pos), "start_time": t64(msgs[0][1]),
                    "end_time": t64(msgs[-1][1]), "count": i32(len(conns))},
                   b"".join(i32(c) + i32(len(v)) for c, v in index.items()))
    hfields = {"op": b"\x03", "index_pos": struct.pack("<Q", index_pos), "conn_count": i32(len(conns)), "chunk_count": i32(1)}
    h = b"".join(field(k, v) for k, v in hfields.items())
    pad = header_len - 8 - len(h)
    header = struct.pack("<i", len(h)) + h + struct.pack("<i", pad) + b" " * pad
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(magic + header + chunk + idx + tail)


def ros1_bags(dest: Path) -> Path:
    root = dest / "ros1_bags"
    hdr_def = "uint32 seq\ntime stamp\nstring frame_id\n"
    conns = [
        ("/vehicle/pose", "geometry_msgs/PoseStamped", "d3812c3cbc69362b77dc0b19b345f8f5",
         "Header header\nPose pose\n\n" + "=" * 80 + "\nMSG: std_msgs/Header\n" + hdr_def + "\n" + "=" * 80 +
         "\nMSG: geometry_msgs/Pose\nPoint position\nQuaternion orientation\n\n" + "=" * 80 +
         "\nMSG: geometry_msgs/Point\nfloat64 x\nfloat64 y\nfloat64 z\n\n" + "=" * 80 +
         "\nMSG: geometry_msgs/Quaternion\nfloat64 x\nfloat64 y\nfloat64 z\nfloat64 w\n"),
        ("/vehicle/speed", "std_msgs/Float32", "73fcbf46b49191e672908e50842a83d4", "float32 data\n"),
        ("/perception/objects", "track_perception_msgs/ObjectArray", "5b0d8f3e9c1a7e44a2c63e1f0d9b8a71",
         "Header header\nObject[] objects\n\n" + "=" * 80 + "\nMSG: std_msgs/Header\n" + hdr_def + "\n" + "=" * 80 +
         "\nMSG: track_perception_msgs/Object\nuint32 id\nstring label\nfloat32 x\nfloat32 y\nfloat32 z\n"
         "float32 vx\nfloat32 vy\nfloat32 confidence\n"),
    ]
    ros_str = lambda s: struct.pack("<I", len(s)) + s.encode()
    ros_hdr = lambda seq, t, frame: struct.pack("<III", seq, t // 1_000_000_000, t % 1_000_000_000) + ros_str(frame)
    local = [("track_2023-05-17_run03.bag", (2023, 5, 17, 14, 2, 11)), ("track_2024-03-08_run01.bag", (2024, 3, 8, 10, 30, 0)),
             ("track_2024-11-21_run05.bag", (2024, 11, 21, 15, 45, 30)), ("track_2025-06-12_run02.bag", (2025, 6, 12, 9, 12, 40))]
    for b, (name, start) in enumerate(local):
        rng = np.random.default_rng(500 + b)
        t0, msgs, x, yaw = _ns(*start), [], 0.0, 0.0
        peds = [(int(rng.integers(1, 50)), float(rng.uniform(10, 40)), float(rng.uniform(-6, 6)), float(rng.uniform(-1.5, 1.5)))
                for _ in range(int(rng.integers(1, 4)))]
        for k in range(200):  # 20 s at 10 Hz
            t = t0 + k * 100_000_000
            v = 9 + 2 * np.sin(k / 30)
            x += v * 0.1
            yaw += 0.002 * np.sin(k / 50)
            msgs.append((0, t, ros_hdr(k, t, "map") + struct.pack("<7d", x, 0.3 * np.sin(k / 40), 0, 0, 0, np.sin(yaw / 2), np.cos(yaw / 2))))
            msgs.append((1, t + 1_000_000, struct.pack("<f", v)))
            objs = []
            for pid, px, py, pvy in peds:
                rx, ry = px - k * 0.1 * 3, py + pvy * k * 0.1
                if -5 < rx < 50 and rng.random() > 0.1:
                    objs.append(struct.pack("<I", pid) + ros_str("pedestrian") + struct.pack("<6f", rx, ry, 0.9, -3.0, pvy, rng.uniform(0.5, 0.95)))
            for j in range(int(rng.integers(1, 4))):
                objs.append(struct.pack("<I", 100 + j) + ros_str("car") + struct.pack("<6f", 20 + 7 * j - k * 0.05, 3.5 * (j % 2), 0.8, 1.0, 0, 0.9))
            msgs.append((2, t + 40_000_000, ros_hdr(k, t, "base_link") + struct.pack("<I", len(objs)) + b"".join(objs)))
        _ros1_bag(root / "bags" / name, conns, msgs)
    rng = np.random.default_rng(42)
    rows = ["bag,recorded_utc,duration_s,size_bytes,location,topics"]
    days = sorted({(int(y), int(m), int(d)) for y, m, d in zip(rng.integers(2022, 2026, 36), rng.integers(1, 13, 36), rng.integers(1, 28, 36))})
    entries = [(n, s, (root / "bags" / n).stat().st_size, "local", "/vehicle/pose;/vehicle/speed;/perception/objects") for n, s in local]
    for y, m, d in days:
        name = f"track_{y}-{m:02d}-{d:02d}_run{int(rng.integers(1, 7)):02d}.bag"
        entries.append((name, (y, m, d, int(rng.integers(8, 18)), int(rng.integers(0, 60)), 0), int(rng.integers(8, 60)) * 1_000_000_000,
                        f"s3://acme-track-archive/bags/{y}/{name}",
                        "/vehicle/pose;/vehicle/speed;/perception/objects;/velodyne_points;/camera/front/image_raw/compressed;/tf"))
    for name, s, size, loc, topics in sorted(entries, key=lambda e: e[1]):
        dur = 20 if loc == "local" else int(size / 9_000_000)
        rows.append(f"{name},{datetime(*s).isoformat()}Z,{dur},{size},{loc},{topics}")
    (root / "bags" / "INDEX.csv").write_text("\n".join(rows) + "\n")
    _write(root / "README.md", '''
        # test-track archive

        ROS1 (Noetic) bags from the test track, 2022 to 2025: 40 bags, listed in `bags/INDEX.csv`.

        - 4 are here in `bags/`, trimmed with `rosbag filter` to `/vehicle/pose`, `/vehicle/speed` and
          `/perception/objects` (track_perception_msgs/ObjectArray).
        - The other 36 are full recordings (lidar, camera, tf) archived in `s3://acme-track-archive/bags/`; fetch with
          `scripts/fetch_bags.sh`.

        The old car PC with ROS Noetic was decommissioned; nothing here has ROS installed.
        ''')
    _write(root / "scripts" / "fetch_bags.sh", '''
        #!/usr/bin/env bash
        # usage: scripts/fetch_bags.sh [pattern]   e.g. 'track_2024-*'
        set -euo pipefail
        aws s3 sync s3://acme-track-archive/bags/ bags/ --exclude '*' --include "*/${1:-*}.bag" --no-progress
        ''')
    return root


_DIRTY_RUN_SUITE = '''
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
    '''


def sim_runner_dirty(dest: Path) -> Path:
    """sim_runner at its commit; _post_commit/ = 3 days of uncommitted tuning (new_workspace.sh applies it after the commit)."""
    import runpy
    root = _derive(sim_runner, dest, "sim_runner_dirty")
    post = root / "_post_commit"
    _write(post / "run_suite.py", _DIRTY_RUN_SUITE)
    suite = runpy.run_path(str(post / "run_suite.py"), run_name="fixture")
    runs = [("20260928-101512", 0.5, None), ("20260928-154003", 0.8, None), ("20260929-093044", 0.8, 0.1),
            ("20260929-162210", 1.0, 0.2), ("20260930-111735", 1.0, 0.3)]
    for stamp, gain, kd in runs:
        for name, w in suite["SCENARIOS"].items():
            out = post / "runs" / stamp / name
            suite["run"](name, w, gain, out, kd or 0.0)
            if kd is None:  # first day: the kd edit didn't exist yet
                res = json.loads((out / "results.json").read_text())
                del res["kd"]
                (out / "results.json").write_text(json.dumps(res))
    return root


def rl_sweep(dest: Path) -> Path:
    root = dest / "rl_sweep"
    _write(root / "README.md", '''
        # ppo-reach sweep

        Learning-rate sweep for PPO on the reach task: 4 learning rates x 3 seeds, 1M env steps each.

        ```
        bash sweep.sh
        ```

        Each run writes `sweep/lr_<lr>/seed_<s>/progress.csv` (step, mean_return, success_rate) every 10k steps,
        plus `config.json`.
        ''')
    _write(root / "sweep.sh", '''
        #!/usr/bin/env bash
        set -euo pipefail
        for lr in 1e-4 3e-4 1e-3 3e-3; do
          for seed in 0 1 2; do
            python train.py --lr "$lr" --seed "$seed" --total-steps 1000000 --out "sweep/lr_${lr}/seed_${seed}"
          done
        done
        ''')
    _write(root / "train.py", '''
        """PPO on ReachTarget-v1. Logs progress.csv every 10k steps."""
        import argparse, csv, json
        from pathlib import Path

        def main() -> None:
            ap = argparse.ArgumentParser()
            ap.add_argument("--lr", type=float, required=True)
            ap.add_argument("--seed", type=int, default=0)
            ap.add_argument("--total-steps", type=int, default=1_000_000)
            ap.add_argument("--out", type=Path, required=True)
            a = ap.parse_args()
            import gymnasium as gym
            from stable_baselines3 import PPO
            from stable_baselines3.common.callbacks import EvalCallback
            a.out.mkdir(parents=True, exist_ok=True)
            cfg = {"algo": "ppo", "env": "ReachTarget-v1", "lr": a.lr, "seed": a.seed, "total_steps": a.total_steps,
                   "n_envs": 8, "batch_size": 256, "gamma": 0.99}
            (a.out / "config.json").write_text(json.dumps(cfg, indent=2) + "\\n")
            env = gym.make_vec("ReachTarget-v1", num_envs=8)
            model = PPO("MlpPolicy", env, learning_rate=a.lr, seed=a.seed, batch_size=256)
            f = open(a.out / "progress.csv", "w", newline="")
            w = csv.writer(f)
            w.writerow(["step", "mean_return", "success_rate"])
            def log(cb):
                w.writerow([cb.num_timesteps, round(cb.last_mean_reward, 3), round(cb.last_success_rate, 3)])
                f.flush()
            model.learn(a.total_steps, callback=EvalCallback(gym.make("ReachTarget-v1"), eval_freq=10_000 // 8, callback_after_eval=log))

        if __name__ == "__main__":
            main()
        ''')
    final = {"1e-4": (62, 0.55, 0.0), "3e-4": (81, 0.84, 0.0), "1e-3": (78, 0.80, 0.0), "3e-3": (48, 0.35, 1.0)}
    for li, (lr, (ret, succ, unstable)) in enumerate(final.items()):
        for seed in range(3):
            rng = np.random.default_rng(100 * li + seed)
            run = root / "sweep" / f"lr_{lr}" / f"seed_{seed}"
            run.mkdir(parents=True)
            steps = np.arange(10_000, 1_000_001, 10_000)
            if lr == "3e-3" and seed == 2:
                steps = steps[steps <= 610_000]  # diverged (NaN loss), run killed
            speed = {"1e-4": 4e-6, "3e-4": 6e-6, "1e-3": 9e-6, "3e-3": 1.2e-5}[lr]
            curve = 1 - np.exp(-steps * speed)
            seed_ret = ret + rng.normal(0, 4 + 6 * unstable)
            mr = -20 + (seed_ret + 20) * curve + rng.normal(0, 2 + 4 * unstable, len(steps))
            if unstable:
                mr -= np.where(steps > 400_000, (steps - 400_000) / 600_000 * 25 * (1 + seed), 0)
            sr = np.clip(succ * curve * (mr + 20) / (ret + 20) + rng.normal(0, 0.02, len(steps)), 0, 1)
            pd.DataFrame({"step": steps, "mean_return": np.round(mr, 3), "success_rate": np.round(sr, 3)}).to_csv(run / "progress.csv", index=False)
            _json(run / "config.json", {"algo": "ppo", "env": "ReachTarget-v1", "lr": float(lr), "seed": seed, "total_steps": 1_000_000,
                                        "n_envs": 8, "batch_size": 256, "gamma": 0.99})
    return root


def harness_no_runs(dest: Path) -> Path:
    root = dest / "harness_no_runs"
    _write(root / "README.md", '''
        # sim harness (WIP)

        Scenario runner for the nav stack sim. Not wired to the simulator yet.

        ```
        python -m harness.run --scenarios harness/scenarios --out results
        ```

        Will write `results/<scenario>/metrics.json` (see `harness/metrics.py`). Plan: run it on every PR.
        ''')
    _write(root / ".gitignore", "__pycache__/\nresults/\n")
    _write(root / "harness" / "__init__.py", "")
    _write(root / "harness" / "metrics.py", '''
        """What each scenario run will report. Fields may still change."""
        import json
        from dataclasses import asdict, dataclass
        from pathlib import Path

        @dataclass
        class ScenarioMetrics:
            scenario: str
            reached_goal: bool
            time_to_goal_s: float
            min_obstacle_distance_m: float
            path_length_m: float
            collisions: int

        def write_metrics(out_dir: Path, m: ScenarioMetrics) -> Path:
            path = out_dir / m.scenario / "metrics.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(m), indent=2) + "\\n")
            return path
        ''')
    _write(root / "harness" / "run.py", '''
        """Run every scenario in the sim and write results/<scenario>/metrics.json."""
        import argparse
        from pathlib import Path
        import yaml
        from harness.metrics import ScenarioMetrics, write_metrics

        def run_scenario(spec: dict) -> ScenarioMetrics:
            # TODO: launch the sim (gazebo headless), spawn the robot at spec["start"], send spec["goal"],
            # record /odom and /scan, compute the metrics.
            raise NotImplementedError("sim not wired up yet")

        def main() -> None:
            ap = argparse.ArgumentParser()
            ap.add_argument("--scenarios", type=Path, default=Path("harness/scenarios"))
            ap.add_argument("--out", type=Path, default=Path("results"))
            a = ap.parse_args()
            for f in sorted(a.scenarios.glob("*.yaml")):
                spec = yaml.safe_load(f.read_text())
                write_metrics(a.out, run_scenario(spec))

        if __name__ == "__main__":
            main()
        ''')
    for name, start, goal, obstacles in [("empty_room", [0, 0, 0], [8, 0], []),
                                         ("narrow_door", [0, 0, 0], [6, 3], [[3, 1.2, 0.4], [3, -0.2, 0.4]]),
                                         ("cluttered_aisle", [0, 0, 1.57], [0, 12], [[0.4, 3, 0.3], [-0.5, 6, 0.3], [0.3, 9, 0.3]])]:
        _write(root / "harness" / "scenarios" / f"{name}.yaml",
               f"name: {name}\nworld: worlds/{name}.world\nstart: {start}\ngoal: {goal}\ntimeout_s: 60\nobstacles: {obstacles}\n")
    return root


# ---- real-pattern cases (mixed_sim_pytest[_integrated], field_uat, video_qa) ----

def mixed_sim_pytest(dest: Path) -> Path:
    root = dest / "mixed_sim_pytest"
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # sim integration tests

        pytest suite against `minisim` (2D diff-drive sim with a topic bus). `pytest` runs everything.

        - `tests/test_timing.py::test_timing_consistency`: clock and odometry stay in step.
        - `tests/test_wall_follow.py::test_wall_follow[offset=...]`: hold a lateral offset from the wall.
        - `tests/test_obstacle_stop.py::test_obstacle_stop[...]`: stop before an obstacle in the path.

        The sim publishes `clock` and `odometry` always; `obstacle_state` only when the world has obstacles.
        ''')
    _write(root / "pyproject.toml", '''
        [project]
        name = "acme-sim-tests"
        version = "0.3.0"
        dependencies = ["numpy"]

        [project.optional-dependencies]
        dev = ["pytest"]
        ''')
    _write(root / "minisim" / "__init__.py", "from minisim.bus import Bus\nfrom minisim.sim import Obstacle, Sim\n")
    _write(root / "minisim" / "bus.py", '''
        from collections import defaultdict

        class Bus:
            """In-process pub/sub. Keeps every message so tests can inspect them."""
            def __init__(self):
                self.messages = defaultdict(list)   # topic -> [(stamp_ns, msg)]
                self._subs = []

            def subscribe(self, fn):
                """fn(topic, stamp_ns, msg) for every message on every topic."""
                self._subs.append(fn)

            def publish(self, topic: str, stamp_ns: int, msg: dict) -> None:
                self.messages[topic].append((stamp_ns, msg))
                for fn in self._subs:
                    fn(topic, stamp_ns, msg)
        ''')
    _write(root / "minisim" / "sim.py", '''
        """Diff-drive robot driving along +x next to a wall at y = 0, optional obstacles ahead."""
        from dataclasses import dataclass
        import numpy as np
        from minisim.bus import Bus

        @dataclass
        class Obstacle:
            name: str
            x: float
            y: float
            radius: float

        class Sim:
            DT = 0.02
            WALL_SENSOR_RANGE_M = 1.0
            OBSTACLE_RATE_HZ = 10

            def __init__(self, bus: Bus, wall_offset: float | None = None, obstacles=(), speed=0.6, seed=0):
                self.bus, self.offset, self.obstacles, self.speed = bus, wall_offset, list(obstacles), speed
                self.rng = np.random.default_rng(seed)
                self.t, self.x, self.y, self.yaw, self.v, self.w = 0.0, 0.0, 0.5 if wall_offset is None else 0.5, 0.0, 0.0, 0.0
                self.k = 0

            def _wall_range(self):
                r = self.y / max(np.cos(self.yaw), 0.2) + self.rng.normal(0, 0.01)
                return r if r < self.WALL_SENSOR_RANGE_M else None

            def step(self):
                target_v = self.speed
                for ob in self.obstacles:
                    d = ob.x - self.x - ob.radius - 0.25
                    if d < 1.5 and abs(ob.y - self.y) < ob.radius + 0.35:
                        target_v = min(target_v, max(0.0, 0.5 * (d - 0.25)))
                self.v += np.clip(target_v - self.v, -1.2 * self.DT, 0.8 * self.DT)
                if self.offset is not None:
                    r = self._wall_range()
                    self.w = 0.0 if r is None else float(np.clip(2.0 * (self.offset - r) - 1.5 * self.yaw, -1, 1))
                self.yaw += self.w * self.DT
                self.x += self.v * np.cos(self.yaw) * self.DT
                self.y += self.v * np.sin(self.yaw) * self.DT
                self.t = round(self.t + self.DT, 6)
                self.k += 1
                ns = int(round(self.t * 1e9))
                self.bus.publish("clock", ns, {"sim_time_s": self.t, "wall_time_s": round(self.t * 1.02, 4), "rtf": 0.98})
                self.bus.publish("odometry", ns, {"x": round(self.x, 4), "y": round(self.y, 4), "yaw": round(self.yaw, 4),
                                                  "vx": round(self.v, 4), "wz": round(self.w, 4)})
                if self.obstacles and self.k % int(1 / (self.DT * self.OBSTACLE_RATE_HZ)) == 0:
                    for ob in self.obstacles:
                        d = float(np.hypot(ob.x - self.x, ob.y - self.y) - ob.radius)
                        self.bus.publish("obstacle_state", ns, {"obstacle_id": ob.name, "distance_m": round(d, 4),
                                                                "relative_speed_mps": round(-self.v, 4),
                                                                "in_path": bool(abs(ob.y - self.y) < ob.radius + 0.35)})

            def run(self, seconds: float):
                for _ in range(int(round(seconds / self.DT))):
                    self.step()
        ''')
    _write(root / "conftest.py", "")
    _write(root / "tests" / "conftest.py", '''
        import pytest
        from minisim import Bus, Sim

        @pytest.fixture
        def bus():
            return Bus()

        @pytest.fixture
        def make_sim(bus):
            def make(**kw):
                return Sim(bus, **kw)
            return make
        ''')
    _write(root / "tests" / "test_timing.py", '''
        import numpy as np

        def test_timing_consistency(make_sim, bus):
            make_sim().run(10.0)
            clock = [m["sim_time_s"] for _, m in bus.messages["clock"]]
            assert np.all(np.diff(clock) > 0)
            assert np.allclose(np.diff(clock), 0.02, atol=1e-6)
            assert len(bus.messages["odometry"]) == len(clock)
            assert min(m["rtf"] for _, m in bus.messages["clock"]) > 0.9
        ''')
    _write(root / "tests" / "test_wall_follow.py", '''
        import numpy as np
        import pytest

        TOLERANCE_M = 0.05

        @pytest.mark.parametrize("offset", [pytest.param(o, id=f"offset={o}") for o in (0.3, 0.5, 0.8, 1.2)])
        def test_wall_follow(make_sim, bus, offset):
            make_sim(wall_offset=offset).run(20.0)
            ys = np.array([m["y"] for _, m in bus.messages["odometry"]][-500:])  # last 10 s
            assert np.mean(np.abs(ys - offset)) < TOLERANCE_M
        ''')
    _write(root / "tests" / "test_obstacle_stop.py", '''
        import pytest
        from minisim import Obstacle

        STOP_MARGIN_M = 0.3
        CASES = {
            "box_2m": [Obstacle("box", 2.0, 0.5, 0.2)],
            "box_4m": [Obstacle("box", 4.0, 0.45, 0.2)],
            "pallet_6m": [Obstacle("pallet", 6.0, 0.6, 0.6), Obstacle("post", 6.5, 2.0, 0.1)],
        }

        @pytest.mark.parametrize("case", list(CASES))
        def test_obstacle_stop(make_sim, bus, case):
            make_sim(obstacles=CASES[case]).run(15.0)
            in_path = [m for _, m in bus.messages["obstacle_state"] if m["in_path"]]
            assert in_path, "obstacle never in path"
            assert min(m["distance_m"] for m in in_path) >= STOP_MARGIN_M
            assert abs(bus.messages["odometry"][-1][1]["vx"]) < 0.01
        ''')
    return root


def mixed_sim_pytest_integrated(dest: Path) -> Path:
    """mixed_sim_pytest + the user's own SignalFlag integration: conftest upload + ONE shared metrics set,
    with obstacle_state metrics that don't skip on tests that never publish it."""
    root = _derive(mixed_sim_pytest, dest, "mixed_sim_pytest_integrated")
    _write(root / "pyproject.toml", '''
        [project]
        name = "acme-sim-tests"
        version = "0.3.0"
        dependencies = ["numpy"]

        [project.optional-dependencies]
        dev = ["pytest"]
        signalflag = ["signalflag==1.8.0"]
        ''')
    readme = (root / "README.md").read_text() + textwrap.dedent('''
        ## SignalFlag

        `SIGNALFLAG_UPLOAD=1 pytest` uploads the session as one batch to project `acme-sim`, branch `sim-int`
        (one SignalFlag test per pytest test; everything the bus carries is emitted). Metrics:
        `.resim/metrics/config.resim.yml`, set `Sim Integration` for every test so all tests look the same.
        ''')
    (root / "README.md").write_text(readme)
    _write(root / "conftest.py", '''
        """Upload each pytest session to SignalFlag. Opt-in: SIGNALFLAG_UPLOAD=1."""
        import os, subprocess, tempfile, time
        from pathlib import Path
        import pytest

        ROOT = Path(__file__).resolve().parent
        UPLOAD = os.environ.get("SIGNALFLAG_UPLOAD") == "1"
        PROJECT, BRANCH, METRICS_SET = "acme-sim", os.environ.get("SIGNALFLAG_BRANCH", "sim-int"), "Sim Integration"
        _sf = {}

        def _git_sha() -> str:
            return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "unknown"

        def pytest_sessionstart(session):
            if not UPLOAD:
                return
            from signalflag.sdk.auth import DeviceCodeClient
            from signalflag.sdk.batch import Batch
            _sf["client"] = DeviceCodeClient()
            _sf["tmp"] = tempfile.mkdtemp(prefix="signalflag-")
            _sf["batch"] = Batch(_sf["client"], project_name=PROJECT, branch=BRANCH, version=_git_sha(),
                                 name=f"pytest {time.strftime('%Y-%m-%d %H:%M')}", metrics_set_name=METRICS_SET,
                                 metrics_config_path=str(ROOT / ".resim/metrics/config.resim.yml"),
                                 templates_path=str(ROOT / ".resim/metrics/templates"))
            _sf["batch"].__enter__()

        def pytest_sessionfinish(session, exitstatus):
            if "batch" in _sf:
                _sf["batch"].__exit__(None, None, None)
                b = _sf["batch"]
                print(f"\\nSignalFlag batch: https://app.signalflag.ai/projects/{b.project_id}/batches/{b.id}")

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(item, call):
            rep = (yield).get_result()
            if rep.when == "call":
                item.sf_report = rep

        @pytest.fixture(autouse=True)
        def signalflag_test(request, bus):
            """One SignalFlag Test per pytest test; every bus message is emitted to its topic."""
            if not UPLOAD:
                yield None
                return
            from signalflag.sdk.test import Test
            cwd = os.getcwd()
            os.chdir(_sf["tmp"])  # emissions files go to cwd
            t = Test(_sf["client"], _sf["batch"], name=request.node.name)
            t.__enter__()
            os.chdir(cwd)
            bus.subscribe(lambda topic, stamp_ns, msg: t.emit(topic, msg, stamp_ns))
            yield t
            rep = getattr(request.node, "sf_report", None)
            t.emit("test_result", {"test": request.node.name, "passed": bool(rep and rep.passed),
                                   "duration_s": float(rep.duration if rep else 0.0)}, time.time_ns())
            os.chdir(_sf["tmp"])
            t.__exit__(None, None, None)
            os.chdir(cwd)
        ''')
    _write(root / ".resim" / "metrics" / "config.resim.yml", '''
        version: 1

        topics:
          clock:
            schema: {sim_time_s: float, wall_time_s: float, rtf: float}
          odometry:
            schema: {x: float, y: float, yaw: float, vx: float, wz: float}
          obstacle_state:
            schema: {obstacle_id: string, distance_m: float, relative_speed_mps: float, in_path: boolean}
          test_result:
            schema: {test: string, passed: boolean, duration_s: float}

        metrics:
          Verdict:
            type: test
            description: Whether the pytest test passed.
            query_string: SELECT CASE WHEN passed THEN 1 ELSE 0 END AS value FROM test_result
            template_type: system
            template: scalar
            skip_if_no_data: false
            status: {query_string: "SELECT 1 FROM test_result WHERE NOT passed AND ? = 0", block: 0}
          Trajectory:
            type: test
            description: Robot position over the run.
            query_string: SELECT 'robot' AS group_name, x AS "x (m)", y AS "y (m)" FROM odometry ORDER BY timestamp
            template_type: system
            template: line
            skip_if_no_data: false
          Speed:
            type: test
            description: Forward speed over time.
            query_string: SELECT 'vx' AS group_name, timestamp / 1E9 AS "Time (s)", vx AS "Speed (m/s)" FROM odometry
            template_type: system
            template: line
            skip_if_no_data: false
          Real-time Factor:
            type: test
            description: Sim time over wall time.
            query_string: SELECT 'rtf' AS group_name, sim_time_s AS "Sim time (s)", rtf AS "RTF" FROM clock
            template_type: system
            template: line
            skip_if_no_data: false
          Min Obstacle Distance:
            type: test
            description: Closest approach to any obstacle in the path.
            query_string: SELECT MIN(distance_m) AS value FROM obstacle_state WHERE in_path
            template_type: system
            template: scalar
            units: m
            skip_if_no_data: false
            status: {query_string: "SELECT 1 FROM (SELECT MIN(distance_m) AS d FROM obstacle_state WHERE in_path) s WHERE s.d < ?", block: 0.3, warn: 0.4}
          Obstacle Distance:
            type: test
            description: Distance to each obstacle over time.
            query_string: SELECT obstacle_id AS group_name, timestamp / 1E9 AS "Time (s)", distance_m AS "Distance (m)" FROM obstacle_state
            template_type: system
            template: line
            skip_if_no_data: false
          Stop Margin:
            type: test
            description: Closest approach minus the 0.3 m stop margin, per obstacle.
            query_string: SELECT obstacle_id AS "Obstacle", MIN(distance_m) - 0.3 AS "Margin (m)" FROM obstacle_state GROUP BY obstacle_id
            template_type: system
            template: table
            skip_if_no_data: false
          Tests Passed:
            type: batch
            description: Passed and failed tests in this session.
            query_string: SELECT CASE WHEN passed THEN 'passed' ELSE 'failed' END AS group_name, 'tests' AS "Result", COUNT(*) AS "Count" FROM test_result GROUP BY 1
            template_type: system
            template: bar
            skip_if_no_data: false
          Pass Rate Trend:
            type: dashboard
            description: Share of tests passing per session.
            query_string: "SELECT 'pass rate' AS group_name, m.build_creation_timestamp AS \\"Build time\\", AVG(CASE WHEN r.passed THEN 1.0 ELSE 0.0 END) AS \\"Pass rate\\" FROM test_result r JOIN metadata m ON m.job_id = r.job_id GROUP BY 2 ORDER BY 2"
            template_type: system
            template: line
            skip_if_no_data: true

        metrics sets:
          Sim Integration:
            metrics: [Verdict, Trajectory, Speed, Real-time Factor, Min Obstacle Distance, Obstacle Distance, Stop Margin, Tests Passed]
          Sim Trends:
            metrics: [Pass Rate Trend]

        dashboards:
          Sim Trends: {metrics_set: Sim Trends, refresh: auto, day_range: 90}
        ''')
    return root


_UAT_CASES = {
    "UAT-003": ("Emergency stop", '''
        **Setup:** open yard, robot driving straight at 1.5 m/s under autonomy.
        **Procedure:** 1. Start mission `uat_straight_40m`. 2. At the cone, press the e-stop on the pendant. 3. Measure the stop.
        **Pass:** robot stops within 1.2 m of the e-stop press; no motion after stop; e-stop state latched until reset.
        '''),
    "UAT-006": ("Autonomous docking", '''
        **Setup:** charging dock D2, robot parked 6-8 m away, battery < 80 %.
        **Procedure:** 1. Send `dock` from the console. 2. Wait for CHARGING or 120 s. 3. Note the alignment marks.
        **Pass:** reaches CHARGING within 90 s, at most one re-try; final lateral alignment within 2 cm (marks on the dock plate).
        '''),
    "UAT-012": ("Obstacle stop", '''
        **Setup:** recorded route R7, test dummy placed on the path 15 m ahead.
        **Procedure:** 1. Run route R7. 2. Observe the stop in front of the dummy. 3. Remove the dummy; robot must resume.
        **Pass:** stops at 0.8 m or more from the dummy; resumes within 5 s of removal.
        '''),
    "UAT-018": ("Path retrace", '''
        **Setup:** teach route T3 (figure of eight, 120 m) by driving it manually.
        **Procedure:** 1. Replay T3 autonomously three times in a row. 2. Watch the wheel tracks against the taught line.
        **Pass:** stays on the taught path (max deviation 15 cm, judged by eye against the chalk line); completes all loops.
        '''),
}


def field_uat(dest: Path) -> Path:
    root = dest / "field_uat"
    _write(root / "README.md", '''
        # rover field acceptance (UAT)

        Before each release a field tech runs the UAT cases in `uat/cases/` on a rover:

        1. Start recording right before the case (`scripts/record_case.sh <release> <case> <robot> <n>`), stop right after.
           Bags land in `field/<release>/<case>_<robot>_<n>.mcap`.
        2. Fill in `field/<release>/results.csv` (case, robot, run, result PASS/FAIL, notes) by hand.

        Releases are tagged like `4.12.0-rc2`.
        ''')
    for case, (title, body) in _UAT_CASES.items():
        _write(root / "uat" / "cases" / f"{case}.md", f"# {case}: {title}\n\n" + textwrap.dedent(body).lstrip())
    _write(root / "scripts" / "record_case.sh", '''
        #!/usr/bin/env bash
        # usage: scripts/record_case.sh <release> <case> <robot> <n>
        set -euo pipefail
        out="field/$1/$2_$3_$4"
        ros2 bag record -s mcap -o "$out" /odom /localization/pose /diagnostics /estop/state \\
          /docking/state /route/status /perception/nearest_obstacle
        mv "$out"/*.mcap "$out.mcap" && rmdir "$out"
        ''')
    sessions = {
        "4.11.0-rc3": ((2026, 8, 18), [("UAT-003", "rover-07", 1, "PASS", ""), ("UAT-006", "rover-07", 1, "FAIL", "stopped 4cm off, retried, timed out"),
                                       ("UAT-006", "rover-07", 2, "PASS", "docked first try"), ("UAT-012", "rover-07", 1, "PASS", ""),
                                       ("UAT-018", "rover-07", 1, "PASS", "")]),
        "4.12.0-rc1": ((2026, 9, 15), [("UAT-003", "rover-11", 1, "PASS", "wet grass"), ("UAT-006", "rover-11", 1, "FAIL", "two retries then gave up"),
                                       ("UAT-012", "rover-11", 1, "PASS", "recording not started, forgot"),
                                       ("UAT-018", "rover-07", 1, "PASS", ""), ("UAT-018", "rover-11", 1, "FAIL", "cut the corner at the top of the 8")]),
        "4.12.0-rc2": ((2026, 9, 26), [("UAT-003", "rover-07", 1, "PASS", ""), ("UAT-006", "rover-07", 1, "PASS", ""),
                                       ("UAT-006", "rover-11", 1, "PASS", "slow approach"), ("UAT-006", "rover-11", 2, "PASS", ""),
                                       ("UAT-012", "rover-07", 1, "PASS", ""),
                                       ("UAT-018", "rover-07", 1, "PASS", "looked fine, slight wobble after loop 2")]),
    }
    for si, (release, (day, rows)) in enumerate(sessions.items()):
        out = root / "field" / release
        out.mkdir(parents=True)
        lines = [["case", "robot", "run", "result", "notes"]]
        for ri, (case, robot, n, verdict, note) in enumerate(rows):
            lines.append([case, robot, n, verdict, note])
            if "recording not started" in note:
                continue
            rng = np.random.default_rng(10_000 + si * 100 + ri)
            t0 = _ns(*day, 9 + ri, int(rng.integers(0, 50)), 0)
            _write_mcap(out / f"{case}_{robot}_{n}.mcap", _uat_records(case, verdict, release, rng, t0))
        _csv(out / "results.csv", lines)
    return root


def _uat_records(case, verdict, release, rng, t0):
    """2 Hz odom/pose, 4 Hz case topic, 0.5 Hz diagnostics, around one UAT case."""
    dur = {"UAT-003": 30, "UAT-006": 50, "UAT-012": 40, "UAT-018": 60}[case]
    if case == "UAT-006" and verdict == "FAIL":
        dur = 70
    recs, n = [], dur * 4
    t = lambda k: t0 + k * 250_000_000
    x = y = v = 0.0
    yaw = 0.0
    estop_k = 40 if case == "UAT-003" else None
    xs = []
    for k in range(n):
        u = k / n
        if case == "UAT-003":
            v = 1.5 if (estop_k is None or k < estop_k) else max(0.0, v - 2.2 * 0.25)
        elif case == "UAT-006":
            v = (14.0 / dur) * (1 - u)  # covers the ~7 m to the dock
        elif case == "UAT-012":
            v = 1.0 if x < 13.8 + rng.normal(0, 0.05) else max(0.0, v - 0.5)
            if k > n * 0.75:
                v = 1.0
        else:
            v = 2.0
            yaw = 1.2 * np.sin(2 * np.pi * 3 * u)
        x += v * np.cos(yaw) * 0.25
        y += v * np.sin(yaw) * 0.25
        xs.append(x)
        if k % 2 == 0:
            recs.append(("/odom", "nav_msgs/msg/Odometry", t(k) + 2_000_000, {
                "header": _hdr(t(k), "odom"), "child_frame_id": "base_link",
                "pose": {"pose": {"position": {"x": _r(x), "y": _r(y), "z": 0.0}, "orientation": _quat_z(yaw)}},
                "twist": {"twist": {"linear": {"x": _r(v), "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}}}))
            recs.append(("/localization/pose", "geometry_msgs/msg/PoseStamped", t(k) + 6_000_000, {
                "header": _hdr(t(k), "map"), "pose": {"position": {"x": _r(x + rng.normal(0, 0.02)), "y": _r(y + rng.normal(0, 0.02)), "z": 0.0},
                                                       "orientation": _quat_z(yaw)}}))
        if k % 8 == 0:
            recs.append(("/diagnostics", "diagnostic_msgs/msg/DiagnosticArray", t(k) + 9_000_000, _diag(t(k), [
                (0, "software", "OK", "rover", {"version": release, "map": "yard_v9"}),
                (0, "battery", "OK", "rover", {"percent": _r(76 - u * 3, 1)})])))
        if k % 4 == 0:
            engaged = estop_k is not None and k >= estop_k
            recs.append(("/estop/state", "acme_rover_msgs/msg/EstopState", t(k) + 1_000_000,
                         {"header": _hdr(t(k), ""), "engaged": engaged, "source": "pendant" if engaged else "none"}))
        if case == "UAT-006":
            fail = verdict == "FAIL"
            dist = max(0.0, 7.0 * (1 - u * (1.0 if not fail else 0.9)))
            state = "APPROACH" if dist > 1.0 else "ALIGN" if dist > 0.05 else "CONTACT" if u < 0.95 else "CHARGING"
            if fail and u > 0.6:
                state = ["ALIGN", "RETRY", "ALIGN", "RETRY", "FAILED"][min(4, int((u - 0.6) / 0.08))]
            lat = 0.15 * (1 - u) + (0.04 if fail else 0.008) + rng.normal(0, 0.002)
            recs.append(("/docking/state", "acme_rover_msgs/msg/DockingState", t(k) + 3_000_000, {
                "header": _hdr(t(k), "dock_d2"), "state": state, "dock_id": "D2", "distance_to_dock_m": _r(dist),
                "lateral_error_m": _r(lat, 4), "yaw_error_rad": _r(0.1 * (1 - u) + rng.normal(0, 0.003), 4), "retries": int(state == "RETRY")}))
        if case == "UAT-018":
            cte = abs(rng.normal(0, 0.03)) + (0.22 * np.exp(-((u - 0.83) / 0.03) ** 2) if verdict == "FAIL" else 0)
            if release == "4.12.0-rc2":
                cte += 0.12 * np.exp(-((u - 0.7) / 0.05) ** 2)  # the "slight wobble": over 15 cm though marked PASS
            recs.append(("/route/status", "acme_rover_msgs/msg/RouteStatus", t(k) + 3_000_000, {
                "header": _hdr(t(k), "map"), "route_id": "T3", "loop": 1 + int(u * 3), "progress": _r(u, 4),
                "cross_track_error_m": _r(cte, 4), "heading_error_rad": _r(rng.normal(0, 0.02), 4)}))
        if case == "UAT-012":
            d = max(0.0, 15.0 - x) if k <= n * 0.75 else 99.0
            recs.append(("/perception/nearest_obstacle", "acme_rover_msgs/msg/NearestObstacle", t(k) + 3_000_000, {
                "header": _hdr(t(k), "base_link"), "distance_m": _r(min(d, 30.0)), "class_id": "person" if d < 30 else "none",
                "in_path": bool(d < 30)}))
    return recs


def video_qa(dest: Path) -> Path:
    root = dest / "video_qa"
    _write(root / "README.md", '''
        # egocentric video deliveries

        Each delivery to a client is `deliveries/<delivery_id>/`:

        - `videos/*.mp4`: head-camera clips, one task per clip (proxy resolution here; full-res stays in the bucket).
        - `annotations.json`: per video `duration_s`, `fps`, `task`, `hand_visibility` segments, collector, device.

        Today QA is someone skimming a sample of clips before we ship. We want every clip checked.
        ''')
    tasks = {"fold_towel": (4.0, 7.0), "pour_water": (2.5, 5.0), "wipe_table": (3.0, 6.0), "stack_cups": (3.5, 6.5), "open_drawer": (1.5, 3.0)}
    for d, (delivery, count, seed) in enumerate([("DLV-2026-0915", 150, 91), ("DLV-2026-0929", 152, 92)]):
        rng = np.random.default_rng(seed)
        fps, size, videos = 15, 64, []
        yy, xx = np.mgrid[0:size, 0:size]
        for v in range(count):
            task = str(rng.choice(list(tasks)))
            lo, hi = tasks[task]
            dur = float(rng.uniform(lo, hi))
            issue = rng.choice(["none", "blur", "drops", "nohands", "short", "long"], p=[0.84, 0.04, 0.04, 0.03, 0.025, 0.025])
            if issue == "short":
                dur = lo * 0.35
            elif issue == "long":
                dur = hi * 2.2
            n = max(int(dur * fps), 8)
            base = np.zeros((size, size, 3), np.float32)
            base[..., 0] = 120 + 60 * (yy / size)
            base[..., 1] = 100 + 40 * (xx / size)
            base[..., 2] = 80
            base[(yy > 40) & (yy < 44)] = (60, 50, 40)  # table edge
            base[(yy > 44)] *= 0.8
            frames = np.empty((n, size, size, 3), np.uint8)
            vis = []
            for k in range(n):
                shake = rng.normal(0, 1.2, 2).astype(int)
                f = np.roll(base, tuple(shake), axis=(0, 1)).copy()
                left = issue != "nohands" and not (0.4 < k / n < 0.55)
                right = issue != "nohands"
                for on, cx in ((left, 20 + 6 * np.sin(k / 6)), (right, 44 + 6 * np.cos(k / 7))):
                    if on:
                        cy = 48 + 4 * np.sin(k / 5)
                        f[(xx - cx) ** 2 + (yy - cy) ** 2 < 36] = (210, 160, 130)
                if issue == "blur":
                    for _ in range(3):
                        f = (f + np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 5
                frames[k] = np.clip(f, 0, 255).astype(np.uint8)
                vis.append((left, right))
            if issue == "drops":  # encoder froze: repeated frames
                for s in rng.choice(np.arange(2, n - 6), size=3, replace=False):
                    frames[s:s + 4] = frames[s]
            name = f"ego_{d + 1}{v:04d}.mp4"
            _mp4(root / "deliveries" / delivery / "videos" / name, frames, fps)
            segs, start = [], 0
            labeled = vis if issue != "nohands" or rng.random() < 0.5 else [(True, True)] * n  # some missing-hand clips mislabeled
            for k in range(1, n + 1):
                if k == n or labeled[k] != labeled[start]:
                    segs.append({"start_s": round(start / fps, 2), "end_s": round(k / fps, 2), "left": bool(labeled[start][0]),
                                 "right": bool(labeled[start][1])})
                    start = k
            videos.append({"file": name, "duration_s": round(n / fps, 2), "fps": fps, "task": task, "hand_visibility": segs,
                           "collector_id": f"C-{int(rng.integers(1, 25)):03d}", "device": str(rng.choice(["headcam-v3", "headcam-v4"]))})
        _json(root / "deliveries" / delivery / "annotations.json", {"delivery_id": delivery, "client": "client-07", "videos": videos})
    return root


# ---- perception_cam: camera 2D detection + tracking replay for a yard vehicle ----

_PC_F, _PC_CX, _PC_CY, _PC_CAM_H, _PC_W, _PC_H, _PC_SCALE = 1600.0, 960.0, 560.0, 1.6, 1920, 1280, 20
_PC_SIZES = {"car": (1.8, 1.5), "truck": (2.5, 3.5), "pedestrian": (0.6, 1.75), "cyclist": (0.7, 1.7)}
_PC_COLORS = {"car": (40, 70, 170), "truck": (215, 140, 40), "pedestrian": (240, 200, 60), "cyclist": (60, 170, 90)}
_PC_SCENES = {"day": ((150, 190, 230), (112, 112, 108)), "rain": ((118, 122, 130), (82, 84, 88)), "night": ((8, 10, 22), (26, 26, 30))}
_PC_HEAVY_RAIN, _PC_SPLASH = range(35, 53), range(61, 66)  # rain_crosswalk frames
_PC_SCENARIOS = {
    # name: (recording start, lighting, weather, description, actors as (class, x0 lateral, z0 forward, vx, vz) in the camera frame)
    "day_parking_lot": ((2026, 9, 14, 15, 2, 10), "day", "clear", "Creeping through the north lot past parked cars, two pedestrians and a cyclist.",
                        [("car", -6, 14, 0, -1), ("car", -6, 21, 0, -1), ("car", -6, 28, 0, -1), ("car", 6.5, 17, 0, -1),
                         ("car", 6.5, 25, 0, -1), ("pedestrian", -3.0, 16, 0.35, -1), ("pedestrian", 2.2, 21, 0, -1),
                         ("cyclist", 0.8, 12, 0, 0.5)]),
    "night_parking_lot": ((2026, 9, 14, 21, 40, 0), "night", "clear", "Same lot after dark (lot lights off), three pedestrians among parked cars.",
                          [("car", -6, 13, 0, -1), ("car", -6, 20, 0, -1), ("car", -6, 27, 0, -1), ("car", 6.5, 16, 0, -1),
                           ("car", 6.5, 24, 0, -1), ("pedestrian", -3.2, 15, 0.35, -1), ("pedestrian", 2.6, 21, -0.3, -1),
                           ("pedestrian", 5.0, 30, 0, -1)]),
    "rain_crosswalk": ((2026, 9, 17, 8, 15, 30), "day", "rain", "Stopped at the gate crosswalk in rain; two pedestrians cross, one waits on the curb, a cyclist waits across the road.",
                       [("pedestrian", -7, 10, 1.2, 0), ("pedestrian", -9.5, 10.5, 1.2, 0), ("pedestrian", 6.5, 15, 0, 0),
                        ("car", -4, 26, 0, 0), ("car", 3.5, 30, 0, 0), ("cyclist", 8, 26, 0, 0)]),
    "crowded_loading_dock": ((2026, 9, 18, 11, 5, 0), "day", "clear", "Waiting at dock 4 during shift change: six workers crossing in both directions.",
                             [("truck", -7.5, 19, 0, 0), ("truck", 7.5, 21, 0, 0),
                              ("pedestrian", -1.5, 8.5, 0.6, 0), ("pedestrian", 1.5, 9.0, -0.6, 0),
                              ("pedestrian", -5, 10, 1.0, 0), ("pedestrian", 4.5, 10.6, -1.0, 0),
                              ("pedestrian", -6.5, 12.2, 0.9, 0), ("pedestrian", 5.5, 12.6, -0.95, 0)]),
    "highway_merge_far": ((2026, 9, 21, 13, 30, 45), "day", "clear", "Merging onto the perimeter road: traffic from 18 m out to 80 m.",
                          [("car", -3.5, 18, 0, 0.4), ("car", 3.5, 28, 0, 0), ("car", 0, 38, 0, -0.8), ("truck", 7, 46, 0, 0.3),
                           ("car", -3.5, 52, 0, 0.5), ("car", 3.5, 62, 0, -1.0), ("truck", -7, 66, 0, -0.5), ("car", 16, 78, 0, -1.0)]),
}


def _pc_box(cls: str, x: float, z: float):
    """Pinhole projection of an upright box on the ground -> bbox in sensor pixels, clipped; None if not visible."""
    if z < 4:
        return None
    w, h = _PC_SIZES[cls]
    u, bot = _PC_CX + _PC_F * x / z, _PC_CY + _PC_F * _PC_CAM_H / z
    x1, x2 = max(0.0, u - _PC_F * w / 2 / z), min(float(_PC_W), u + _PC_F * w / 2 / z)
    y1, y2 = max(0.0, bot - _PC_F * h / z), min(float(_PC_H), bot)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return {"x_min": _r(x1, 1), "y_min": _r(y1, 1), "x_max": _r(x2, 1), "y_max": _r(y2, 1)}


def _pc_frame(lighting: str, weather: str, objs, k: int, rng, splash: bool):
    """Clean 96x64 preview of the front camera: sky, ground, objects far-to-near, rain streaks."""
    from PIL import Image, ImageDraw
    sky, ground = _PC_SCENES["night" if lighting == "night" else ("rain" if weather == "rain" else "day")]
    img = Image.new("RGB", (_PC_W // _PC_SCALE, _PC_H // _PC_SCALE), ground)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 95, int(_PC_CY / _PC_SCALE) - 1], fill=sky)
    d.line([(0, 52), (95, 52)], fill=tuple(int(c * 1.25) for c in ground))  # painted stop line
    for o in sorted(objs, key=lambda o: -o["range_m"]):
        b = {k_: v / _PC_SCALE for k_, v in o["bbox_2d"].items()}
        scale = 0.3 if lighting == "night" else (0.85 if weather == "rain" else 1.0)
        col = tuple(int(c * scale) for c in _PC_COLORS[o["class"]])
        x1, y1, x2, y2 = int(b["x_min"]), int(b["y_min"]), max(int(b["x_min"]), int(round(b["x_max"])) - 1), max(int(b["y_min"]), int(round(b["y_max"])) - 1)
        d.rectangle([x1, y1, x2, y2], fill=col)
        if lighting == "night" and o["class"] in ("car", "truck"):
            d.point([(x1, y2 - 1), (x2, y2 - 1)], fill=(255, 200, 140))
    if weather == "rain":
        for _ in range(45 if k in _PC_HEAVY_RAIN else 6):
            x, y, n = int(rng.integers(0, 96)), int(rng.integers(0, 60)), int(rng.integers(3, 7))
            d.line([(x, y), (x, y + n)], fill=(176, 179, 186))
    if splash:  # headlight glare off a puddle
        d.rectangle([70, 37, 72, 41], fill=(255, 255, 255))
    return img


def perception_cam(dest: Path) -> Path:
    import base64
    root = dest / "perception_cam"
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # yard-perception replay

        Camera perception (2D detection + tracking) for the acme autonomous yard tractor. Recorded front-camera drives are
        replayed through the perception stack and everything it publishes is recorded.

        ```
        python replay/run_replay.py --scenario day_parking_lot   # one scenario
        python replay/run_replay.py                              # all of them
        docker compose run --rm replay                           # same thing, in the release image
        ```

        - `scenarios/<name>.yaml`: what each drive is (site, lighting, weather) and where its recording + labels live.
        - `recordings/<name>.mcap`: the recorded input, `/camera/front/image` (JPEG) at 10 Hz, 8 s per drive.
        - `labels/<name>.jsonl`: ground truth from the labeling vendor, one line per camera frame:
          `{"frame", "stamp", "objects": [{"object_id", "class", "bbox_2d", "range_m"}]}`.
        - `outputs/<name>/replay.mcap`: what the stack published during the last replay (overwritten each run):
          `/camera/front/image` (annotated preview), `/perception/detections`, `/perception/tracks`,
          `/perception/latency`, `/diagnostics`. Also `camera.mp4` (annotated preview) and `replay.gif` (every 4th frame).
        - `perception/stack.py`: CPU stand-in for the stack in `acme/perception` (so the harness runs on a laptop).
        - `perception/eval_utils.py`: IoU + greedy matcher for scoring against the labels.

        Classes: car, pedestrian, cyclist, truck. `bbox_2d` is `{x_min, y_min, x_max, y_max}` in sensor pixels (1920x1280);
        the JPEGs are 96x64 previews (sensor / 20). `range_m` is distance from the camera. Track `age` is in frames.
        End-to-end latency budget (camera stamp to tracks out): 100 ms.

        TODO: score replays against the labels (nobody has wired this up yet).
        ''')
    _write(root / "compose.yaml", '''
        # Replay one scenario in the release image: SCENARIO=rain_crosswalk docker compose run --rm replay
        name: yard-perception-replay

        services:
          replay:
            image: acme/perception:2026.09.4
            working_dir: /work
            command: python replay/run_replay.py --scenario ${SCENARIO:-day_parking_lot}
            volumes:
              - ./scenarios:/work/scenarios:ro
              - ./recordings:/work/recordings:ro
              - ./labels:/work/labels:ro
              - ./replay:/work/replay:ro
              - ./outputs:/work/outputs
        ''')
    _write(root / "perception" / "__init__.py", "")
    _write(root / "perception" / "stack.py", '''
        """CPU stand-in for the acme camera perception stack (acme/perception image): detector + tracker.

        The release stack runs a TensorRT detector on the full-resolution camera. This module reproduces its interface and
        its measured behaviour (bench calibration of the 2026.09 model) so the replay harness runs anywhere: the detector
        is a sensor model over the objects in view, plus the image-dependent parts (scene brightness, the derain
        pre-filter, bright clutter).
        """
        import numpy as np

        CLASSES = ("car", "pedestrian", "cyclist", "truck")
        PREVIEW_SCALE = 20  # preview px -> sensor px (96x64 -> 1920x1280)
        SIZES = {"car": (1.8, 1.5), "truck": (2.5, 3.5), "pedestrian": (0.6, 1.75), "cyclist": (0.7, 1.7)}
        FOCAL_PX, HORIZON_PX, CAMERA_HEIGHT_M = 1600.0, 560.0, 1.6

        DETECTOR = {
            "score_threshold": 0.3,
            "recall": {"car": 0.97, "truck": 0.97, "pedestrian": 0.96, "cyclist": 0.95},
            "full_recall_range_m": 38.0, "range_falloff_m": 7.0,
            "low_light_luminance": 60.0, "low_light_recall": {"car": 0.97, "truck": 0.97, "pedestrian": 0.22, "cyclist": 0.5},
            "occluded_fraction": 0.6, "occluded_recall": 0.2, "nms_iou": 0.3,
            "box_jitter": 0.04, "range_jitter": 0.03,
        }
        TRACKER = {"iou_gate": 0.3, "min_hits": 3, "max_misses": 4, "publish_max_misses": 1}
        LATENCY = {"base_ms": 38.0, "per_detection_ms": 2.2, "jitter_ms": 3.0,
                   "derain_trigger_px": 90, "derain_ms": 70.0, "budget_ms": 100.0}


        def iou(a: dict, b: dict) -> float:
            ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
            iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
            inter = ix * iy
            area = lambda r: (r["x_max"] - r["x_min"]) * (r["y_max"] - r["y_min"])
            return inter / (area(a) + area(b) - inter) if inter > 0 else 0.0


        def _covered(a: dict, b: dict) -> float:
            """Fraction of box a covered by box b."""
            ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
            iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
            return ix * iy / max(1e-6, (a["x_max"] - a["x_min"]) * (a["y_max"] - a["y_min"]))


        def _r(x, n=1):
            return round(float(x), n)


        class Tracker:
            """Greedy IoU tracker (constant-position prediction). Confirmed after min_hits consecutive hits; published while
                updated this frame or coasting through one missed frame."""

            def __init__(self):
                self.tracks, self.next_id = [], 1

            def update(self, dets: list) -> list:
                pairs = sorted(((iou(t["bbox_2d"], d["bbox_2d"]), ti, di) for ti, t in enumerate(self.tracks)
                                for di, d in enumerate(dets) if t["class"] == d["class"]), reverse=True)
                used_t, used_d = set(), set()
                for s, ti, di in pairs:
                    if s < TRACKER["iou_gate"] or ti in used_t or di in used_d:
                        continue
                    used_t.add(ti), used_d.add(di)
                    t, d = self.tracks[ti], dets[di]
                    t.update(bbox_2d=d["bbox_2d"], range_m=d["range_m"], hits=t["hits"] + 1, misses=0)
                for ti, t in enumerate(self.tracks):
                    t["age"] += 1
                    if ti not in used_t:
                        t["misses"] += 1
                self.tracks = [t for t in self.tracks if t["misses"] == 0 or  # tentative tracks die on their first miss
                               (t["hits"] >= TRACKER["min_hits"] and t["misses"] <= TRACKER["max_misses"])]
                for di, d in enumerate(dets):
                    if di not in used_d:
                        self.tracks.append({"track_id": self.next_id, "class": d["class"], "bbox_2d": d["bbox_2d"],
                                            "range_m": d["range_m"], "age": 0, "hits": 1, "misses": 0})
                        self.next_id += 1
                return [{k: t[k] for k in ("track_id", "class", "bbox_2d", "range_m", "age")} for t in self.tracks
                        if t["hits"] >= TRACKER["min_hits"] and t["misses"] <= TRACKER["publish_max_misses"]]


        class PerceptionStack:
            def __init__(self, seed: int):
                self.rng = np.random.default_rng(seed)
                self.tracker = Tracker()

            def _detect(self, objects: list, low_light: bool) -> list:
                c, dets = DETECTOR, []
                for o in sorted(objects, key=lambda o: o["range_m"]):
                    u = self.rng.random(4)
                    p = (c["low_light_recall"] if low_light else c["recall"])[o["class"]]
                    if o["range_m"] > c["full_recall_range_m"]:
                        p *= np.exp(-(o["range_m"] - c["full_recall_range_m"]) / c["range_falloff_m"])
                    if any(_covered(o["bbox_2d"], n["bbox_2d"]) > c["occluded_fraction"]
                           for n in objects if n["range_m"] < o["range_m"]):
                        p *= c["occluded_recall"]
                    if u[0] >= p:
                        continue
                    b = o["bbox_2d"]
                    w, h = b["x_max"] - b["x_min"], b["y_max"] - b["y_min"]
                    j = self.rng.normal(0, c["box_jitter"], 4)
                    box = {"x_min": _r(b["x_min"] + j[0] * w), "y_min": _r(b["y_min"] + j[1] * h),
                           "x_max": _r(b["x_max"] + j[2] * w), "y_max": _r(b["y_max"] + j[3] * h)}
                    score = float(np.clip(0.82 + 0.06 * self.rng.standard_normal(), 0.31, 0.99))
                    dets.append({"class": o["class"], "score": _r(score, 3), "bbox_2d": box,
                                 "range_m": _r(o["range_m"] * (1 + c["range_jitter"] * (2 * u[1] - 1)), 2)})
                return dets

            @staticmethod
            def _nms(dets: list) -> list:
                """Class-wise non-maximum suppression, highest score first."""
                keep = []
                for d in sorted(dets, key=lambda d: -d["score"]):
                    if all(k["class"] != d["class"] or iou(k["bbox_2d"], d["bbox_2d"]) <= DETECTOR["nms_iou"] for k in keep):
                        keep.append(d)
                return keep

            def _clutter(self, rgb: np.ndarray) -> list:
                """Saturated blobs (glare, reflections) fire the pedestrian head."""
                ys, xs = np.nonzero(rgb.min(axis=2) > 225)
                if len(xs) < 4:
                    return []
                s = PREVIEW_SCALE
                y2 = (ys.max() + 1) * s
                h = y2 - ys.min() * s
                cx = (xs.min() + xs.max() + 1) / 2 * s
                rng_m = FOCAL_PX * CAMERA_HEIGHT_M / max(1.0, y2 - HORIZON_PX)
                return [{"class": "pedestrian", "score": _r(0.55 + 0.1 * self.rng.random(), 3),
                         "bbox_2d": {"x_min": _r(cx - 0.18 * h), "y_min": _r(y2 - h), "x_max": _r(cx + 0.18 * h), "y_max": _r(y2)},
                         "range_m": _r(rng_m, 2)}]

            def step(self, image, objects: list) -> dict:
                """image: PIL preview of the camera frame; objects: what is in view (label format)."""
                rgb = np.asarray(image.convert("RGB")).astype(np.int16)
                lum = rgb @ np.array([299, 587, 114]) / 1000
                low_light = lum.mean() < DETECTOR["low_light_luminance"]
                streak_px = int(((lum[:, 1:-1] - np.maximum(lum[:, :-2], lum[:, 2:])) > 20).sum())  # thin vertical streaks
                derain = streak_px > LATENCY["derain_trigger_px"]
                dets = self._detect(objects, low_light) + self._clutter(rgb)
                dets = self._nms([d for d in dets if d["score"] >= DETECTOR["score_threshold"]])
                tracks = self.tracker.update(dets)
                ms = LATENCY["base_ms"] + LATENCY["per_detection_ms"] * len(dets) + LATENCY["jitter_ms"] * self.rng.standard_normal()
                if derain:
                    ms += LATENCY["derain_ms"] + 8.0 * self.rng.standard_normal()
                return {"detections": dets, "tracks": tracks, "e2e_ms": round(float(ms), 2), "derain": bool(derain),
                        "low_light": bool(low_light)}
        ''')
    _write(root / "perception" / "eval_utils.py", '''
        """Helpers for scoring a replay against labels/<scenario>.jsonl."""
        import json
        from pathlib import Path


        def iou(a: dict, b: dict) -> float:
            """IoU of two {x_min, y_min, x_max, y_max} boxes."""
            ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
            iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
            inter = ix * iy
            area = lambda r: (r["x_max"] - r["x_min"]) * (r["y_max"] - r["y_min"])
            return inter / (area(a) + area(b) - inter) if inter > 0 else 0.0


        def match(gt: list, pred: list, iou_threshold: float = 0.5, class_aware: bool = True):
            """Greedy one-to-one matching, highest IoU first.
            gt / pred: lists of dicts with "bbox_2d" (and "class").
            Returns (matches [(gt_index, pred_index, iou)], unmatched_gt [index], unmatched_pred [index])."""
            pairs = sorted(((iou(g["bbox_2d"], p["bbox_2d"]), gi, pi) for gi, g in enumerate(gt) for pi, p in enumerate(pred)
                            if not class_aware or g["class"] == p["class"]), reverse=True)
            used_g, used_p, matches = set(), set(), []
            for s, gi, pi in pairs:
                if s < iou_threshold or gi in used_g or pi in used_p:
                    continue
                used_g.add(gi), used_p.add(pi)
                matches.append((gi, pi, s))
            return (matches, [i for i in range(len(gt)) if i not in used_g], [i for i in range(len(pred)) if i not in used_p])


        def load_labels(path) -> list:
            """labels/<scenario>.jsonl -> list of {"frame", "stamp", "objects"} in frame order."""
            return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


        def stamp_ns(stamp: dict) -> int:
            return int(stamp["sec"]) * 1_000_000_000 + int(stamp["nanosec"])
        ''')
    _write(root / "replay" / "run_replay.py", '''
        """Replay recorded scenarios through the perception stack and record what it publishes.

        For each scenarios/<name>.yaml: plays recordings/<name>.mcap frame by frame and writes
          outputs/<name>/replay.mcap  (/camera/front/image annotated, /perception/detections, /perception/tracks,
                                       /perception/latency, /diagnostics)
          outputs/<name>/camera.mp4   (annotated preview, 10 fps)
          outputs/<name>/replay.gif   (every 4th annotated frame)
        """
        import argparse, base64, io, json, shutil, subprocess, sys, zlib
        from pathlib import Path

        import numpy as np
        import yaml
        from mcap.reader import make_reader
        from mcap.writer import CompressionType, Writer
        from PIL import Image, ImageDraw

        ROOT = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(ROOT))
        from perception.stack import LATENCY, PREVIEW_SCALE, PerceptionStack  # noqa: E402

        STACK = "acme/perception:2026.09.4"
        _STAMP = {"type": "object", "properties": {"sec": {"type": "integer"}, "nanosec": {"type": "integer"}}}
        _HEADER = {"type": "object", "properties": {"stamp": _STAMP, "frame_id": {"type": "string"}}}
        _BOX = {"type": "object", "properties": {k: {"type": "number"} for k in ("x_min", "y_min", "x_max", "y_max")}}
        _CLASS = {"type": "string", "enum": ["car", "pedestrian", "cyclist", "truck"]}
        SCHEMAS = {
            "/camera/front/image": ("sensor_msgs/msg/CompressedImage", {"header": _HEADER, "format": {"type": "string"},
                                                                       "data": {"type": "string", "contentEncoding": "base64"}}),
            "/perception/detections": ("acme_perception_msgs/msg/Detection2DArray", {"header": _HEADER, "detections": {
                "type": "array", "items": {"type": "object", "properties": {
                    "class": _CLASS, "score": {"type": "number"}, "bbox_2d": _BOX, "range_m": {"type": "number"}}}}}),
            "/perception/tracks": ("acme_perception_msgs/msg/Track2DArray", {"header": _HEADER, "tracks": {
                "type": "array", "items": {"type": "object", "properties": {
                    "track_id": {"type": "integer"}, "class": _CLASS, "bbox_2d": _BOX, "range_m": {"type": "number"},
                    "age": {"type": "integer"}}}}}),
            "/perception/latency": ("acme_perception_msgs/msg/Latency", {"header": _HEADER, "input_stamp": _STAMP,
                                                                         "output_stamp": _STAMP, "e2e_ms": {"type": "number"}}),
            "/diagnostics": ("diagnostic_msgs/msg/DiagnosticArray", {"header": _HEADER, "status": {"type": "array", "items": {
                "type": "object", "properties": {"level": {"type": "integer"}, "name": {"type": "string"},
                                                 "message": {"type": "string"}, "hardware_id": {"type": "string"},
                                                 "values": {"type": "array", "items": {"type": "object", "properties": {
                                                     "key": {"type": "string"}, "value": {"type": "string"}}}}}}}}),
        }


        def _stamp(ns: int) -> dict:
            return {"sec": ns // 1_000_000_000, "nanosec": ns % 1_000_000_000}


        def _annotate(img: Image.Image, dets: list) -> Image.Image:
            out = img.copy()
            d = ImageDraw.Draw(out)
            for det in dets:
                b = det["bbox_2d"]
                d.rectangle([int(b["x_min"] / PREVIEW_SCALE), int(b["y_min"] / PREVIEW_SCALE),
                             max(int(b["x_min"] / PREVIEW_SCALE), int(b["x_max"] / PREVIEW_SCALE) - 1),
                             max(int(b["y_min"] / PREVIEW_SCALE), int(b["y_max"] / PREVIEW_SCALE) - 1)],
                            outline=(0, 255, 0) if det["class"] != "pedestrian" else (255, 0, 255))
            return out


        def _jpeg(img: Image.Image) -> bytes:
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=55, optimize=True)
            return buf.getvalue()


        def _write_mcap(path: Path, records: list) -> None:
            with open(path, "wb") as f:
                w = Writer(f, compression=CompressionType.NONE)
                w.start(profile="ros2", library="acme-replay 1.3.0")
                ids = {}
                for topic, (name, props) in SCHEMAS.items():
                    sid = w.register_schema(name=name, encoding="jsonschema", data=json.dumps(
                        {"title": name, "type": "object", "properties": props}, sort_keys=True).encode())
                    ids[topic] = w.register_channel(topic=topic, message_encoding="json", schema_id=sid)
                seq = {}
                for t, order, topic, msg in sorted(records, key=lambda r: (r[0], r[1])):
                    seq[topic] = seq.get(topic, 0) + 1
                    w.add_message(ids[topic], log_time=t, publish_time=t, sequence=seq[topic],
                                  data=json.dumps(msg, separators=(",", ":")).encode())
                w.finish()


        def _mp4(path: Path, frames: list, fps: int = 10) -> None:
            a = np.stack([np.asarray(f) for f in frames])
            n, h, w, _ = a.shape
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                            "-pix_fmt", "yuv420p", "-threads", "1", "-bitexact", "-fflags", "+bitexact",
                            "-flags:v", "+bitexact", "-map_metadata", "-1", str(path)], input=a.tobytes(), check=True)


        def replay(scenario: Path) -> None:
            sc = yaml.safe_load(scenario.read_text())
            name = sc["name"]
            labels = {}
            for line in (ROOT / sc["labels"]).read_text().splitlines():
                row = json.loads(line)
                labels[row["stamp"]["sec"] * 1_000_000_000 + row["stamp"]["nanosec"]] = row["objects"]
            stack = PerceptionStack(seed=zlib.crc32(name.encode()))
            out = ROOT / "outputs" / name
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir(parents=True)
            records, frames, warn = [], [], 0
            with open(ROOT / sc["recording"], "rb") as f:
                for _, ch, m in make_reader(f).iter_messages(topics=["/camera/front/image"]):
                    msg = json.loads(m.data)
                    t_in = msg["header"]["stamp"]["sec"] * 1_000_000_000 + msg["header"]["stamp"]["nanosec"]
                    img = Image.open(io.BytesIO(base64.b64decode(msg["data"]))).convert("RGB")
                    r = stack.step(img, labels.get(t_in, []))
                    t_out = t_in + int(round(r["e2e_ms"] * 1e6))
                    hdr_in, hdr_out = {"stamp": _stamp(t_in), "frame_id": "camera_front"}, {"stamp": _stamp(t_out), "frame_id": "camera_front"}
                    shown = _annotate(img, r["detections"])
                    frames.append(shown)
                    over = r["e2e_ms"] > LATENCY["budget_ms"]
                    warn += over
                    records += [
                        (t_out, 0, "/camera/front/image", {"header": hdr_in, "format": "jpeg",
                                                           "data": base64.b64encode(_jpeg(shown)).decode()}),
                        (t_out, 1, "/perception/detections", {"header": hdr_in, "detections": r["detections"]}),
                        (t_out, 2, "/perception/tracks", {"header": hdr_in, "tracks": r["tracks"]}),
                        (t_out, 3, "/perception/latency", {"header": hdr_out, "input_stamp": _stamp(t_in),
                                                           "output_stamp": _stamp(t_out), "e2e_ms": r["e2e_ms"]}),
                        (t_out, 4, "/diagnostics", {"header": hdr_out, "status": [{
                            "level": 1 if over else 0, "name": "perception/stack", "hardware_id": "orin-0",
                            "message": f"e2e latency {r['e2e_ms']:.1f} ms over {LATENCY['budget_ms']:.0f} ms budget" if over else "OK",
                            "values": [{"key": "e2e_ms", "value": f"{r['e2e_ms']:.2f}"},
                                       {"key": "derain", "value": str(r["derain"]).lower()},
                                       {"key": "detections", "value": str(len(r["detections"]))}]}]}),
                    ]
            _write_mcap(out / "replay.mcap", records)
            _mp4(out / "camera.mp4", frames)
            frames[0].save(out / "replay.gif", save_all=True, append_images=frames[4::4], duration=400, loop=0)
            print(f"[replay] {name}: {len(frames)} frames through {STACK} -> {out.relative_to(ROOT)}/ ({warn} diagnostics WARN)")


        if __name__ == "__main__":
            ap = argparse.ArgumentParser()
            ap.add_argument("--scenario", action="append", help="scenario name (repeatable); default: all")
            a = ap.parse_args()
            names = a.scenario or sorted(p.stem for p in (ROOT / "scenarios").glob("*.yaml"))
            for n in names:
                replay(ROOT / "scenarios" / f"{n}.yaml")
        ''')
    for name, (start, lighting, weather, desc, actors) in _PC_SCENARIOS.items():
        _write(root / "scenarios" / f"{name}.yaml", f'''
            name: {name}
            description: "{desc}"
            site: acme yard 3
            vehicle: yt-07
            recorded_at: "{datetime(*start, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}"
            duration_s: 8.0
            conditions:
              lighting: {lighting}
              weather: {weather}
            recording: recordings/{name}.mcap
            labels: labels/{name}.jsonl
            camera:
              topic: /camera/front/image
              rate_hz: 10
              sensor_px: [1920, 1280]
              preview_px: [96, 64]
            ''')
        rng = np.random.default_rng(int.from_bytes(name.encode()[:4], "little"))
        t0, recs, lines = _ns(*start), [], []
        for k in range(80):
            t = t0 + k * 100_000_000
            objs = []
            for oid, (cls, x0, z0, vx, vz) in enumerate(actors, 1):
                x, z = x0 + vx * k * 0.1, z0 + vz * k * 0.1
                box = _pc_box(cls, x, z)
                if box:
                    objs.append({"object_id": oid, "class": cls, "bbox_2d": box, "range_m": _r(np.hypot(x, z), 2)})
            lines.append(json.dumps({"frame": k, "stamp": _hdr(t, "")["stamp"], "objects": objs}, separators=(",", ":")))
            img = _pc_frame(lighting, weather, objs, k, rng, name == "rain_crosswalk" and k in _PC_SPLASH)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=55, optimize=True)
            recs.append(("/camera/front/image", "sensor_msgs/msg/CompressedImage", t,
                         {"header": _hdr(t, "camera_front"), "format": "jpeg", "data": base64.b64encode(buf.getvalue()).decode()}))
            if k % 10 == 0:
                recs.append(("/camera/front/camera_info", "sensor_msgs/msg/CameraInfo", t, {
                    "header": _hdr(t, "camera_front"), "height": _PC_H, "width": _PC_W, "distortion_model": "plumb_bob",
                    "k": [_PC_F, 0.0, _PC_CX, 0.0, _PC_F, _PC_CY, 0.0, 0.0, 1.0]}))
        _write_mcap(root / "recordings" / f"{name}.mcap", recs)
        (root / "labels").mkdir(exist_ok=True)
        (root / "labels" / f"{name}.jsonl").write_text("\n".join(lines) + "\n")
    _run_py(root, "replay/run_replay.py")
    _clean_pycache(root)
    return root


# ---- image_set_eval: offline 2D detector evaluation on a labeled photo set ----

_ISE_W, _ISE_H, _ISE_SCALE = 960, 640, 10  # label/prediction pixel space; images/ holds 96x64 previews (/10)
_ISE_SOURCES = {  # source: (id prefix, count, {condition: share}, class mix, first day)
    "dashcam_a": ("da", 90, {"day": 0.55, "night": 0.25, "fog": 0.20}, {"car": 0.6, "pedestrian": 0.25, "truck": 0.15}, 2),
    "dashcam_b": ("db", 90, {"day": 0.55, "night": 0.25, "fog": 0.20}, {"car": 0.6, "pedestrian": 0.25, "truck": 0.15}, 9),
    "warehouse_cam": ("wh", 60, {"day": 0.75, "night": 0.25}, {"forklift": 0.5, "pedestrian": 0.35, "truck": 0.15}, 16),
}
_ISE_ASPECT = {"car": 1.6, "pedestrian": 0.4, "truck": 1.3, "forklift": 0.9}  # w / h
_ISE_COLORS = {"car": (40, 70, 170), "pedestrian": (240, 200, 60), "truck": (215, 140, 40), "forklift": (200, 40, 40)}
_ISE_MODELS = {  # recall by GT size, condition, class; TP score mean; FP rate per image
    "det-v4.1": {"size": {"small": 0.72, "medium": 0.86, "large": 0.90}, "cond": {"day": 1.0, "night": 0.90, "fog": 0.85},
                 "cls": {"forklift": 0.35}, "score": 0.72, "fp": 0.6},
    "det-v4.2": {"size": {"small": 0.48, "medium": 0.96, "large": 0.98}, "cond": {"day": 1.0, "night": 0.93, "fog": 0.58},
                 "cls": {"forklift": 1.0}, "score": 0.80, "fp": 0.4},
}
_ISE_LABEL_ERRORS = 8


def _ise_size(w, h) -> str:
    a = w * h
    return "small" if a < 32 ** 2 else ("medium" if a < 96 ** 2 else "large")


def _ise_iou(a, b) -> float:
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / (a[2] * a[3] + b[2] * b[3] - i) if i else 0.0


def _ise_preview(source, cond, objs):
    from PIL import Image, ImageDraw
    if source == "warehouse_cam":
        top, floor = ((150, 145, 135), (120, 110, 95)) if cond == "day" else ((60, 58, 55), (48, 44, 38))
    else:
        top, floor = {"day": ((150, 190, 230), (100, 100, 98)), "night": ((10, 12, 25), (28, 28, 32)),
                      "fog": ((185, 188, 192), (150, 152, 155))}[cond]
    img = Image.new("RGB", (96, 64), floor)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 95, 27], fill=top)
    if source != "warehouse_cam":
        d.line([(48, 28), (20, 63)], fill=tuple(min(255, c + 60) for c in floor))
        d.line([(48, 28), (76, 63)], fill=tuple(min(255, c + 60) for c in floor))
    for cls, (x, y, w, h) in sorted(objs, key=lambda o: o[1][1] + o[1][3]):  # far (higher) first
        col = _ISE_COLORS[cls]
        if cond == "night":
            col = tuple(int(c * 0.35) for c in col)
        elif cond == "fog":
            col = tuple(int(0.45 * c + 0.55 * 185) for c in col)
        s = _ISE_SCALE
        d.rectangle([int(x / s), int(y / s), max(int(x / s), int((x + w) / s) - 1), max(int(y / s), int((y + h) / s) - 1)], fill=col)
    return img


def image_set_eval(dest: Path) -> Path:
    root = dest / "image_set_eval"
    rng = np.random.default_rng(4242)
    _write(root / ".gitignore", "__pycache__/\n")
    _write(root / "README.md", '''
        # det-v4 offline eval

        Offline evaluation of the acme 2D detector on the frozen photo set `acme-eval-2026.09` (not a replay: one
        labeled photo per file).

        ```
        python eval.py                         # every model under predictions/
        python eval.py --model det-v4.2 --score-thr 0.5
        ```

        - `images/<source>/<id>.jpg`: 96x64 previews (the full-res set stays in the bucket). Sources: dashcam_a,
          dashcam_b, warehouse_cam.
        - `meta.csv`: `id, source, condition (day/night/fog), timestamp` per image.
        - `labels/<id>.json`: COCO-style ground truth, `bbox` = `[x, y, w, h]` in full-res pixels (960x640).
          Classes: car, pedestrian, truck, forklift.
        - `predictions/<model_version>/<id>.json`: detector output for the same image (`bbox`, `category`, `score`),
          exported at score >= 0.05. `predictions/<model_version>/manifest.json` says where it came from.
        - `eval.py`: matches predictions to labels (IoU >= 0.5, greedy by score) and prints AP per class, mAP and
          precision/recall at a score threshold.

        Release question: ship det-v4.2 (retrained with the new warehouse data) to replace det-v4.1?
        ''')
    _write(root / "eval.py", '''
        """Score detector predictions against labels. Prints AP@0.5 per class, mAP, and P/R at a score threshold."""
        import argparse, csv, json
        from pathlib import Path

        ROOT = Path(__file__).resolve().parent
        CLASSES = ["car", "pedestrian", "truck", "forklift"]


        def iou(a, b) -> float:
            """IoU of two [x, y, w, h] boxes."""
            ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
            iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
            i = ix * iy
            return i / (a[2] * a[3] + b[2] * b[3] - i) if i else 0.0


        def load_meta() -> dict:
            with open(ROOT / "meta.csv") as f:
                return {r["id"]: r for r in csv.DictReader(f)}


        def load(kind: str, image_id: str, model: str = "") -> dict:
            p = ROOT / "labels" / f"{image_id}.json" if kind == "labels" else ROOT / "predictions" / model / f"{image_id}.json"
            return json.loads(p.read_text())


        def match_image(gt: list, preds: list, iou_thr: float = 0.5):
            """Greedy, highest score first, same class. Returns (pred_tp flags, gt_matched flags)."""
            order = sorted(range(len(preds)), key=lambda i: -preds[i]["score"])
            used, tp = set(), [False] * len(preds)
            for pi in order:
                best, bi = iou_thr, None
                for gi, g in enumerate(gt):
                    if gi in used or g["category"] != preds[pi]["category"]:
                        continue
                    s = iou(g["bbox"], preds[pi]["bbox"])
                    if s >= best:
                        best, bi = s, gi
                if bi is not None:
                    used.add(bi)
                    tp[pi] = True
            return tp, [gi in used for gi in range(len(gt))]


        def average_precision(scored: list, n_gt: int) -> float:
            """scored: [(score, is_tp)]. All-point interpolated AP."""
            if not n_gt:
                return float("nan")
            tp = fp = 0
            pts = []
            for _, t in sorted(scored, key=lambda x: -x[0]):
                tp, fp = tp + t, fp + (not t)
                pts.append((tp / n_gt, tp / (tp + fp)))
            ap, prev_r = 0.0, 0.0
            for i, (r, _) in enumerate(pts):
                p = max(q for _, q in pts[i:])
                ap += (r - prev_r) * p
                prev_r = r
            return ap


        def evaluate(model: str, score_thr: float = 0.5, iou_thr: float = 0.5) -> dict:
            scored = {c: [] for c in CLASSES}
            n_gt = {c: 0 for c in CLASSES}
            tp = {c: 0 for c in CLASSES}
            fp = {c: 0 for c in CLASSES}
            for image_id in load_meta():
                gt = load("labels", image_id)["annotations"]
                preds = load("predictions", image_id, model)["detections"]
                flags, _ = match_image(gt, preds, iou_thr)
                for g in gt:
                    n_gt[g["category"]] += 1
                for p, t in zip(preds, flags):
                    scored[p["category"]].append((p["score"], t))
                # thresholded P/R: re-match only the kept predictions
                kept = [p for p in preds if p["score"] >= score_thr]
                kflags, _ = match_image(gt, kept, iou_thr)
                for p, t in zip(kept, kflags):
                    (tp if t else fp)[p["category"]] += 1
            ap = {c: average_precision(scored[c], n_gt[c]) for c in CLASSES}
            return {"model": model, "mAP50": sum(ap.values()) / len(ap), "AP50": ap, "n_gt": n_gt,
                    "precision": {c: tp[c] / max(1, tp[c] + fp[c]) for c in CLASSES},
                    "recall": {c: tp[c] / max(1, n_gt[c]) for c in CLASSES},
                    "overall_precision": sum(tp.values()) / max(1, sum(tp.values()) + sum(fp.values())),
                    "overall_recall": sum(tp.values()) / max(1, sum(n_gt.values()))}


        if __name__ == "__main__":
            ap = argparse.ArgumentParser()
            ap.add_argument("--model", action="append", help="model version under predictions/ (repeatable); default: all")
            ap.add_argument("--score-thr", type=float, default=0.5)
            ap.add_argument("--iou", type=float, default=0.5)
            a = ap.parse_args()
            models = a.model or sorted(p.name for p in (ROOT / "predictions").iterdir() if p.is_dir())
            for m in models:
                r = evaluate(m, a.score_thr, a.iou)
                print(f"{m}: mAP@{a.iou:g} {r['mAP50']:.3f}  P {r['overall_precision']:.3f}  R {r['overall_recall']:.3f}"
                      f"  (score >= {a.score_thr:g}, {sum(r['n_gt'].values())} labeled objects)")
                for c in CLASSES:
                    print(f"  {c:10s} AP {r['AP50'][c]:.3f}  P {r['precision'][c]:.3f}  R {r['recall'][c]:.3f}  n={r['n_gt'][c]}")
        ''')
    meta, images = [["id", "source", "condition", "timestamp"]], []
    for source, (prefix, count, conds, mix, day) in _ISE_SOURCES.items():
        cond_list = [c for c, share in conds.items() for _ in range(round(share * count))]
        cond_list = list(rng.permutation(cond_list))
        for i in range(count):
            iid, cond = f"{prefix}_{i + 1:04d}", str(cond_list[i])
            hour = {"day": 9 + i % 8, "night": 20 + i % 4, "fog": 6 + i % 3}[cond]
            ts = datetime(2026, 9, day + i // 15, hour, (7 * i) % 60, (13 * i) % 60, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            meta.append([iid, source, cond, ts])
            objs = []
            for _ in range(int(rng.integers(1, 6))):
                cls = str(rng.choice(list(mix), p=list(mix.values())))
                for _try in range(20):
                    h = float(np.exp(rng.uniform(np.log(28), np.log(260))))
                    if cls in ("car", "truck", "forklift"):
                        h *= 0.7
                    w = h * _ISE_ASPECT[cls]
                    ybot = 280 + (h / 260) * 340 + rng.uniform(-10, 10)  # bigger = closer = lower in frame
                    x, y = float(rng.uniform(0, _ISE_W - w)), float(min(_ISE_H, ybot) - h)
                    box = [round(x, 1), round(max(0.0, y), 1), round(w, 1), round(h, 1)]
                    if all(_ise_iou(box, b) < 0.05 for _, b in objs):
                        objs.append((cls, box))
                        break
            images.append({"id": iid, "source": source, "condition": cond, "objs": objs, "errors": []})
    # label errors (8 images): one object's box was drawn on empty background; the object itself is unlabeled
    cands = [k for k, im in enumerate(images) if im["condition"] != "fog" and
             any(c != "forklift" and _ise_size(b[2], b[3]) != "small" for c, b in im["objs"])]
    for im in [images[j] for j in sorted(rng.choice(cands, _ISE_LABEL_ERRORS, replace=False))]:
        oi = next(k for k, (c, b) in enumerate(im["objs"]) if c != "forklift" and _ise_size(b[2], b[3]) != "small")
        w, h = im["objs"][oi][1][2:]
        for _try in range(200):
            box = [round(float(rng.uniform(0, _ISE_W - w)), 1), round(float(rng.uniform(280, _ISE_H - h)), 1), w, h]
            if all(_ise_iou(box, b) == 0 for _, b in im["objs"]):
                im["errors"].append((oi, box))
                break
    _csv(root / "meta.csv", meta)
    for im in images:
        img = _ise_preview(im["source"], im["condition"], im["objs"])
        (root / "images" / im["source"]).mkdir(parents=True, exist_ok=True)
        img.save(root / "images" / im["source"] / f"{im['id']}.jpg", "JPEG", quality=60, optimize=True)
        wrong = dict(im["errors"])
        anns = [{"id": k + 1, "category": c, "bbox": wrong.get(k, b), "area": round(b[2] * b[3], 1), "iscrowd": 0}
                for k, (c, b) in enumerate(im["objs"])]
        _json(root / "labels" / f"{im['id']}.json", {"image_id": im["id"], "file_name": f"images/{im['source']}/{im['id']}.jpg",
                                                     "width": _ISE_W, "height": _ISE_H, "annotations": anns})
    for mi, (model, cfg) in enumerate(_ISE_MODELS.items()):
        mrng = np.random.default_rng(5000 + mi)
        _json(root / "predictions" / model / "manifest.json", {
            "model_version": model, "checkpoint": f"s3://acme-ml/detector/{model}/model.onnx", "input_px": [_ISE_W, _ISE_H],
            "eval_set": "acme-eval-2026.09", "score_export_min": 0.05,
            "exported_at": "2026-09-24T10:00:00Z" if model == "det-v4.1" else "2026-09-29T16:30:00Z"})
        for im in images:
            dets = []
            wrong = dict(im["errors"])
            for k, (cls, (x, y, w, h)) in enumerate(im["objs"]):
                u = mrng.random(6)
                p = cfg["size"][_ise_size(w, h)] * cfg["cond"][im["condition"]] * cfg["cls"].get(cls, 1.0)
                if u[0] >= p and k not in wrong:  # the mislabeled objects are plain to see: both models find them
                    continue
                j = mrng.normal(0, 0.06, 4) * [w, h, w, h] + mrng.normal(0, 1.0, 4)
                score = cfg["score"] - (0.12 if _ise_size(w, h) == "small" else 0) + 0.1 * mrng.standard_normal()
                if k in wrong:
                    score = 0.86 + 0.05 * mrng.standard_normal()
                dets.append({"category": cls, "bbox": [round(x + j[0], 1), round(y + j[1], 1), round(max(4.0, w + j[2]), 1),
                                                      round(max(4.0, h + j[3]), 1)], "score": round(float(np.clip(score, 0.06, 0.99)), 3)})
            for _ in range(int(mrng.poisson(cfg["fp"]))):  # background false positives (never on a labeled box)
                cls = str(mrng.choice(list(_ISE_ASPECT)))
                h = float(mrng.uniform(30, 150))
                box = [round(float(mrng.uniform(0, _ISE_W - h)), 1), round(float(mrng.uniform(200, _ISE_H - h)), 1),
                       round(h * _ISE_ASPECT[cls], 1), round(h, 1)]
                score = float(np.clip(0.3 + 0.15 * mrng.standard_normal(), 0.05, 0.95))
                if all(_ise_iou(box, b) < 0.1 for b in [b for _, b in im["objs"]] + [b for _, b in im["errors"]]):
                    dets.append({"category": cls, "bbox": box, "score": round(score, 3)})
            dets.sort(key=lambda d: -d["score"])
            _json(root / "predictions" / model / f"{im['id']}.json", {"image_id": im["id"], "model_version": model, "detections": dets})
    return root


# ---- dispatch ----


def _derived(dest: Path, base, name: str) -> Path:
    """Build `base` in a temp dir and copy it to dest/name (derived fixtures add files on top)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src = base(Path(td))
        root = dest / name
        shutil.copytree(src, root)
    return root


def behavior_ci_known_failures(dest: Path) -> Path:
    """behavior_ci + a known-failures list: tracked bugs that run nightly but must not gate a release."""
    root = _derived(dest, behavior_ci, "behavior_ci_known_failures")
    res = {p.stem: json.loads(p.read_text()) for p in sorted((root / "results").glob("*.json")) if p.stem != "summary"}
    failing = sorted(k for k, r in res.items() if r.get("pass") is False)
    passing = sorted(k for k, r in res.items() if r.get("pass") is True)
    known = [(sid, f"PLAN-{412 + i}", "2026-09-0" + str(1 + i)) for i, sid in enumerate(failing[:4])]
    fixed = [(sid, f"PLAN-{390 + i}", "2026-08-2" + str(1 + i)) for i, sid in enumerate(passing[5:7])]  # now passing
    lines = ["# Scenarios that fail for known, ticketed reasons. They run every night but are excluded from the",
             "# release gate (see README). Remove an entry once its ticket is closed and it passes.", "known_failures:"]
    for sid, t, since in known + fixed:
        lines.append(f"  - {{scenario_id: {sid}, ticket: {t}, since: {since}}}")
    _write(root / "known_failures.yaml", "\n".join(lines) + "\n")
    readme = (root / "README.md").read_text()
    _write(root / "README.md", readme + """
## Known failures

`known_failures.yaml` lists scenarios that fail for ticketed reasons. They still run every night, but the
release job ignores them when deciding pass/fail. Nobody checks the list regularly, so some entries may already pass.
""")
    return root


def perception_cam_sim(dest: Path) -> Path:
    """perception_cam + the same stack replayed on sim-rendered drives (a second source/modality of one system)."""
    root = _derived(dest, perception_cam, "perception_cam_sim")
    for real, simname in (("day_parking_lot", "sim_lot_day"), ("night_parking_lot", "sim_lot_night"),
                          ("rain_crosswalk", "sim_crosswalk_rain")):
        (root / "sim" / "outputs" / simname).mkdir(parents=True, exist_ok=True)
        shutil.copy(root / "outputs" / real / "replay.mcap", root / "sim" / "outputs" / simname / "replay.mcap")
        shutil.copy(root / "outputs" / real / "camera.mp4", root / "sim" / "outputs" / simname / "camera.mp4")
        (root / "sim" / "labels").mkdir(parents=True, exist_ok=True)
        shutil.copy(root / "labels" / f"{real}.jsonl", root / "sim" / "labels" / f"{simname}.jsonl")
        _write(root / "sim" / "scenarios" / f"{simname}.yaml", f"""
            name: {simname}
            source: sim   # rendered in the yard digital twin; labels are exact (from the simulator)
            mirrors: {real}
            """)
    _write(root / "sim" / "README.md", """
        # Sim replays

        The same perception stack (`acme/perception`, tag in ../compose.yaml) run on drives rendered in the yard
        digital twin. `python ../replay/run_replay.py --source sim` writes `sim/outputs/<scenario>/`. Labels come
        straight from the simulator, so they're exact. The real-drive replays are in ../outputs/.
        """)
    return root


FIXTURES = (rl_project, pytest_suite, parquet_dump, sim_runner,
            ros2_replay, perception_det, loc_bench, field_mcap, lerobot_act, robomimic_h5, behavior_ci, hil_bench,
            rl_project_with_brief, pytest_suite_with_brief_plus_sim, monorepo, ros1_bags, sim_runner_dirty, rl_sweep,
            harness_no_runs, mixed_sim_pytest, mixed_sim_pytest_integrated, field_uat, video_qa, perception_cam,
            image_set_eval, behavior_ci_known_failures, perception_cam_sim)

if __name__ == "__main__":
    dest = Path(sys.argv[1])
    only = set(sys.argv[2:])  # optional fixture names
    for make in FIXTURES:
        if only and make.__name__ not in only:
            continue
        shutil.rmtree(dest / make.__name__, ignore_errors=True)
        print(make(dest))

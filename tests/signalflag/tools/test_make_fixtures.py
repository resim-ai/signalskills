import json, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest
import make_fixtures as mf


@pytest.fixture
def out(tmp_path):
    return tmp_path


def test_rl_project_eval_folders_lack_checkpoint_step(out):
    root = mf.rl_project(out)
    evals = sorted((root / "evals").iterdir())
    assert len(evals) == 4
    for e in evals:
        df = pd.read_csv(e / "episodes.csv")
        assert list(df.columns) == ["seed", "return", "success", "episode_len"]
        assert "ckpt" not in e.name
    logs = [e / "log.txt" for e in evals if (e / "log.txt").exists()]
    assert len(logs) == 3
    assert "loaded checkpoints/ckpt_" in logs[0].read_text()


def test_rl_project_own_tests_pass(out):
    root = mf.rl_project(out)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(root / "tests")], cwd=root)
    assert r.returncode == 0


def test_pytest_suite_has_one_case_below_threshold(out):
    root = mf.pytest_suite(out)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=root, capture_output=True, text=True)
    assert "1 failed" in r.stdout and "3 passed" in r.stdout
    assert "optional-dependencies" in (root / "pyproject.toml").read_text()


def test_parquet_dump_second_generation_adds_a_field(out):
    root = mf.parquet_dump(out)
    first = pd.read_parquet(root / "telemetry" / "drive_01.parquet")
    later = pd.read_parquet(root / "telemetry_v2" / "drive_04.parquet")
    assert {"t_ns", "speed_mps", "cmd_speed_mps", "battery_pct", "mode"} == set(first.columns)
    assert set(later.columns) - set(first.columns) == {"motor_temp_c"}


def test_sim_runner_writes_150_frames_and_results(out):
    root = mf.sim_runner(out)
    r = subprocess.run([sys.executable, "run_suite.py", "--gain", "0.8"], cwd=root)
    assert r.returncode == 0
    runs = sorted((root / "runs").iterdir())
    assert [p.name for p in runs] == ["corner", "slalom", "straight"]
    for run in runs:
        assert len(list((run / "frames").glob("*.png"))) == 150
        res = json.loads((run / "results.json").read_text())
        assert {"scenario", "gain", "final_error_m", "sim_duration_s"} <= res.keys()
        assert (run / "telemetry.csv").exists()


# ---- robotics fixtures: built once per session ----

import csv, shutil, struct
import h5py
import pyarrow.parquet as pq
import yaml
from mcap.reader import make_reader

NEW = ["ros2_replay", "perception_det", "loc_bench", "field_mcap", "lerobot_act", "robomimic_h5", "behavior_ci", "hil_bench",
       "rl_project_with_brief", "pytest_suite_with_brief_plus_sim", "monorepo", "ros1_bags", "sim_runner_dirty", "rl_sweep",
       "harness_no_runs", "mixed_sim_pytest", "mixed_sim_pytest_integrated", "field_uat", "video_qa", "perception_cam",
       "image_set_eval"]
SKT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    dest = tmp_path_factory.mktemp("fixtures")
    return {name: getattr(mf, name)(dest) for name in NEW}


def _topics(path):
    s = make_reader(open(path, "rb")).get_summary()
    return {c.topic: s.statistics.channel_message_counts.get(i, 0) for i, c in s.channels.items()}


def _first(path, topic):
    for _, _, m in make_reader(open(path, "rb")).iter_messages(topics=[topic]):
        return json.loads(m.data)


def _pytest(root, *args):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=root,
                          capture_output=True, text=True)


def test_every_case_fixture_is_generated():
    cases = yaml.safe_load((SKT / "eval" / "onboard" / "cases.yaml").read_text())
    names = {f.__name__ for f in mf.FIXTURES}
    assert {c["fixture"] for c in cases} <= names


def test_sizes(built):
    total = 0
    for name, root in built.items():
        size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        assert size < 3_000_000, name
        total += size
    assert total < 25_000_000


def test_ros2_replay(built):
    root = built["ros2_replay"]
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    assert compose["services"]["perception"]["profiles"] == ["replay"]
    assert "perception/stack:2026.09.3" in compose["services"]["perception"]["image"]
    outs = sorted((root / "outputs").glob("*/output.mcap"))
    assert len(outs) == 4 == len(list((root / "scenarios").glob("*.mcap")))
    assert _topics(outs[0]) == {"/perception/detections": 120, "/perception/tracks": 120}
    det = _first(outs[0], "/perception/detections")
    assert {"header", "detections"} <= det.keys() and det["detections"][0]["class_id"]
    assert "commit" not in (outs[0].parent / "replay.log").read_text()


def test_perception_det(built):
    root = built["perception_det"]
    evals = sorted((root / "eval").iterdir(), key=lambda p: int(p.name))
    assert [p.name for p in evals] == ["5", "10", "15", "20", "25", "30"]
    assert {p.name for p in (root / "eval" / "20").glob("metrics_*.json")} == {"metrics_day.json", "metrics_night.json"}
    m = {e: {s: json.loads((root / "eval" / str(e) / f"metrics_{s}.json").read_text())["mean_ap"] for s in ("day", "night")} for e in (15, 30)}
    assert m[30]["day"] > m[15]["day"] and m[30]["night"] < m[15]["night"]  # night regresses while day improves
    r = subprocess.run([sys.executable, "eval.py", "--ckpt", "runs/centerpoint_v3/ckpt_25.pth", "--out", "/tmp/_pd_eval"], cwd=root)
    assert r.returncode == 0
    shutil.rmtree("/tmp/_pd_eval")


def test_loc_bench(built):
    root = built["loc_bench"]
    seqs = sorted(p.name for p in (root / "sequences").iterdir())
    assert seqs == ["corridor_long", "ramp_up", "warehouse_loop", "yard_figure8"]
    for s in seqs:
        assert (root / "sequences" / s / "groundtruth.txt").read_text().startswith("# timestamp tx ty tz qx qy qz qw")
        assert (root / "sequences" / s / "estimate.txt").exists()
    assert "ATE_MAX_M = 0.15" in (root / "tests" / "test_bench.py").read_text()
    r = _pytest(root, "tests")
    assert "1 failed, 7 passed" in r.stdout and "test_rpe[yard_figure8]" in r.stdout


def test_field_mcap(built):
    root = built["field_mcap"]
    logs = sorted((root / "logs").glob("*/*.mcap"))
    assert len(logs) == 7
    for log in logs:
        t = _topics(log)
        assert {"/odom", "/localization/pose", "/diagnostics", "/teleop/takeover"} <= t.keys()
        assert ("/gps/fix" in t) == (log.parent.name == "amr-03")
    old = _first(root / "logs" / "amr-01" / "2026-09-21.mcap", "/localization/pose")
    new = _first(root / "logs" / "amr-01" / "2026-09-24.mcap", "/localization/pose")
    assert set(new) - set(old) == {"match_score"}  # localizer rollout adds a field


def test_lerobot_act(built):
    root = built["lerobot_act"]
    for ds, eps in (("data", 18), ("eval_data", 40)):
        info = json.loads((root / ds / "meta" / "info.json").read_text())
        assert info["total_episodes"] == eps and info["codebase_version"] == "v2.1"
        assert len((root / ds / "meta" / "episodes.jsonl").read_text().splitlines()) == eps
        t = pq.read_table(root / ds / "data" / "chunk-000" / "episode_000000.parquet")
        assert set(t.column_names) == {"observation.state", "action", "timestamp", "frame_index", "episode_index", "index", "task_index"}
        assert (root / ds / "videos" / "chunk-000" / "observation.images.top" / f"episode_{eps - 1:06d}.mp4").stat().st_size > 1000
    rows = list(csv.DictReader(open(root / "real_evals" / "080000.csv")))
    assert len(rows) == 10 and set(rows[0]) == {"trial", "success", "time_s", "notes"}
    assert (root / "outputs/train/act_pick_cube/checkpoints/100000/pretrained_model/model.safetensors").exists()


def test_robomimic_h5(built):
    root = built["robomimic_h5"]
    files = sorted((root / "rollouts").glob("epoch_*.hdf5"))
    assert [f.name for f in files] == ["epoch_100.hdf5", "epoch_200.hdf5", "epoch_300.hdf5"]
    with h5py.File(files[0]) as f:
        demos = f["data"]
        assert len(demos) == 150
        g = demos["demo_0"]
        assert {"obs", "actions", "rewards", "dones"} <= set(g)
        tasks = [demos[k].attrs["task"] for k in demos]
        assert {t: tasks.count(t) for t in set(tasks)} == {"lift": 50, "can": 50, "square": 50}
        assert "success" in g.attrs


def test_behavior_ci(built):
    root = built["behavior_ci"]
    scen = list((root / "scenarios").rglob("*.yaml"))
    res = [p for p in (root / "results").glob("*.json") if p.name != "summary.json"]
    assert len(scen) == len(res) == 412
    r = json.loads(res[0].read_text())
    assert {"pass", "min_ttc_s", "max_decel", "collisions", "route_completion"} <= r.keys()
    assert "<testcase" in (root / "results" / "junit.xml").read_text()
    assert "rc-*" in (root / ".github" / "workflows" / "release.yml").read_text()
    out = root.parent / "_bci_out"
    p = subprocess.run([sys.executable, "-m", "simtest", "run", "scenarios/", "--out", str(out), "--filter", "cut_in_00"], cwd=root)
    assert p.returncode in (0, 1) and len(list(out.glob("cut_in_00*.json"))) == 9


def test_hil_bench(built):
    root = built["hil_bench"]
    assert json.loads((root / "out" / "device.json").read_text())["firmware"] == "2.7.1"
    assert (root / "out" / "test_step_response[3000rpm]" / "trace.csv").read_text().startswith("t_s,current_a,velocity_rpm")
    junit = (root / "out" / "junit.xml").read_text()
    assert junit.count("<failure") == 1 and "test_step_response[3000rpm]" in junit
    assert "pytest tests/hil -m hil --junitxml=out/junit.xml" in (root / "Jenkinsfile").read_text()


def test_brief_variants(built):
    rl = built["rl_project_with_brief"]
    brief = (rl / "docs" / "signalflag" / "checkpoint-eval-test-brief.md").read_text()
    assert "approved" in brief and "_pending: signalflag-design-metrics_" in brief and "acme-robotics" in brief
    assert len(list((rl / "evals").iterdir())) == 4
    ps = built["pytest_suite_with_brief_plus_sim"]
    brief = (ps / "docs" / "signalflag" / "planner-test-brief.md").read_text()
    assert "planner-ci" in brief and "_pending: signalflag" not in brief
    assert len(list((ps / "sim" / "runs").iterdir())) == 2
    r = _pytest(ps, "tests")
    assert "1 failed, 3 passed" in r.stdout


def test_monorepo(built):
    root = built["monorepo"]
    assert len(list((root / "perception" / "outputs").glob("*/output.mcap"))) == 3
    assert (root / "perception" / "compose.yaml").exists()
    r = _pytest(root / "planning", "tests")
    assert "1 failed, 8 passed" in r.stdout


def _read_bag(path):
    """Minimal ROS1 bag v2 reader: walk the records, return (conn topics, message count)."""
    data = path.read_bytes()
    assert data[:13] == b"#ROSBAG V2.0\n"
    pos, topics, n = 13, {}, 0
    def rec(p):
        hl = struct.unpack_from("<i", data, p)[0]
        h, p = data[p + 4:p + 4 + hl], p + 4 + hl
        dl = struct.unpack_from("<i", data, p)[0]
        fields, i = {}, 0
        while i < len(h):
            fl = struct.unpack_from("<i", h, i)[0]
            k, v = h[i + 4:i + 4 + fl].split(b"=", 1)
            fields[k.decode()] = v
            i += 4 + fl
        return fields, data[p + 4:p + 4 + dl], p + 4 + dl
    hdr, _, pos = rec(pos)
    assert hdr["op"] == b"\x03" and pos == 13 + 4096
    index_pos = struct.unpack("<Q", hdr["index_pos"])[0]
    chunk, body, _ = rec(pos)
    assert chunk["op"] == b"\x05" and chunk["compression"] == b"none"
    p = 0
    while p < len(body):
        f, _, p2 = None, None, None
        hl = struct.unpack_from("<i", body, p)[0]
        h = body[p + 4:p + 4 + hl]
        dl = struct.unpack_from("<i", body, p + 4 + hl)[0]
        if b"op=\x02" in h:
            n += 1
        p += 8 + hl + dl
    q = index_pos
    while q < len(data):
        f, d, q = rec(q)
        if f["op"] == b"\x07":
            topics[struct.unpack("<i", f["conn"])[0]] = f["topic"].decode()
    return topics, n


def test_ros1_bags(built):
    root = built["ros1_bags"]
    bags = sorted((root / "bags").glob("*.bag"))
    assert len(bags) == 4
    topics, n = _read_bag(bags[0])
    assert set(topics.values()) == {"/vehicle/pose", "/vehicle/speed", "/perception/objects"} and n == 600
    index = list(csv.DictReader(open(root / "bags" / "INDEX.csv")))
    assert len(index) == 40 and sum(r["location"] == "local" for r in index) == 4


def test_sim_runner_dirty_keeps_edits_out_of_the_commit(built):
    root = built["sim_runner_dirty"]
    assert "--kd" not in (root / "run_suite.py").read_text()
    post = root / "_post_commit"
    assert "--kd" in (post / "run_suite.py").read_text()
    runs = sorted((post / "runs").iterdir())
    assert [r.name[:8] for r in runs] == ["20260928", "20260928", "20260929", "20260929", "20260930"]
    assert "kd" not in json.loads((runs[0] / "corner" / "results.json").read_text())
    assert "kd" in json.loads((runs[-1] / "corner" / "results.json").read_text())


def test_new_workspace_applies_post_commit():
    ws = Path(subprocess.run(["bash", str(SKT / "tools" / "new_workspace.sh"), "sim_runner_dirty", "_test-dirty"],
                             capture_output=True, text=True, check=True).stdout.strip())
    try:
        assert not (ws / "_post_commit").exists()
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True, text=True).stdout
        assert " M run_suite.py" in status and "?? runs/" in status
        tracked = subprocess.run(["git", "ls-files"], cwd=ws, capture_output=True, text=True).stdout
        assert "_post_commit" not in tracked
    finally:
        shutil.rmtree(ws)


def test_rl_sweep(built):
    root = built["rl_sweep"]
    runs = sorted((root / "sweep").glob("lr_*/seed_*/progress.csv"))
    assert len(runs) == 12
    df = pd.read_csv(runs[0])
    assert list(df.columns) == ["step", "mean_return", "success_rate"]
    assert {p.parent.parent.name for p in runs} == {"lr_1e-4", "lr_3e-4", "lr_1e-3", "lr_3e-3"}


def test_harness_no_runs(built):
    root = built["harness_no_runs"]
    assert (root / "harness" / "run.py").exists() and not (root / "results").exists()
    assert not list(root.rglob("metrics.json"))


def test_mixed_sim_pytest(built):
    for name in ("mixed_sim_pytest", "mixed_sim_pytest_integrated"):
        root = built[name]
        r = _pytest(root, "-rA", "tests")
        for tid in ("test_timing_consistency", "test_wall_follow[offset=0.3]", "test_wall_follow[offset=1.2]",
                    "test_obstacle_stop[box_2m]", "test_obstacle_stop[pallet_6m]"):
            assert tid in r.stdout, (name, tid)
        assert "1 failed, 7 passed" in r.stdout
    sys.path.insert(0, str(built["mixed_sim_pytest"]))
    try:
        from minisim import Bus, Obstacle, Sim
        b = Bus(); Sim(b, wall_offset=0.5).run(2.0)
        assert "obstacle_state" not in b.messages
        b = Bus(); Sim(b, obstacles=[Obstacle("box", 2.0, 0.5, 0.2)]).run(2.0)
        assert b.messages["obstacle_state"]
    finally:
        sys.path.pop(0)
        for m in [m for m in sys.modules if m.startswith("minisim")]:
            del sys.modules[m]
    integ = built["mixed_sim_pytest_integrated"]
    conftest = (integ / "conftest.py").read_text()
    assert "from signalflag.sdk.batch import Batch" in conftest and "from signalflag.sdk.test import Test" in conftest
    cfg = yaml.safe_load((integ / ".resim" / "metrics" / "config.resim.yml").read_text())
    assert list(cfg["metrics sets"]) == ["Sim Integration", "Sim Trends"]
    obstacle = [k for k, m in cfg["metrics"].items() if "obstacle_state" in m["query_string"]]
    assert obstacle and all(cfg["metrics"][k]["skip_if_no_data"] is False for k in obstacle)
    assert set(obstacle) <= set(cfg["metrics sets"]["Sim Integration"]["metrics"])


def test_field_uat(built):
    root = built["field_uat"]
    assert {p.stem for p in (root / "uat" / "cases").glob("*.md")} >= {"UAT-006", "UAT-018"}
    for rel in ("4.11.0-rc3", "4.12.0-rc1", "4.12.0-rc2"):
        rows = list(csv.DictReader(open(root / "field" / rel / "results.csv")))
        assert set(rows[0]) == {"case", "robot", "run", "result", "notes"}
        mcaps = {p.name for p in (root / "field" / rel).glob("*.mcap")}
        assert mcaps <= {f"{r['case']}_{r['robot']}_{r['run']}.mcap" for r in rows}
    assert "/docking/state" in _topics(root / "field" / "4.12.0-rc2" / "UAT-006_rover-07_1.mcap")
    assert not (root / "field" / "4.12.0-rc1" / "UAT-012_rover-11_1.mcap").exists()  # row without a recording


def test_video_qa(built):
    root = built["video_qa"]
    for d in ("DLV-2026-0915", "DLV-2026-0929"):
        ann = json.loads((root / "deliveries" / d / "annotations.json").read_text())
        vids = sorted((root / "deliveries" / d / "videos").glob("*.mp4"))
        assert len(vids) == len(ann["videos"]) >= 150
        v = ann["videos"][0]
        assert {"file", "duration_s", "fps", "task", "hand_visibility"} <= v.keys()
        assert (root / "deliveries" / d / "videos" / v["file"]).exists()


def test_perception_cam(built, tmp_path):
    import numpy as np
    root = built["perception_cam"]
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    assert compose["services"]["replay"]["image"] == "acme/perception:2026.09.4"
    names = sorted(p.stem for p in (root / "scenarios").glob("*.yaml"))
    assert len(names) == 5 and "rain_crosswalk" in names
    assert not list(root.rglob("FAULTS*"))
    for n in names:
        out = root / "outputs" / n
        assert {p.name for p in out.iterdir()} == {"replay.mcap", "camera.mp4", "replay.gif"}
        assert _topics(out / "replay.mcap") == {t: 80 for t in ("/camera/front/image", "/perception/detections",
                                                              "/perception/tracks", "/perception/latency", "/diagnostics")}
        assert len((root / "labels" / f"{n}.jsonl").read_text().splitlines()) == 80
        lat = [json.loads(m.data)["e2e_ms"] for _, _, m in make_reader(open(out / "replay.mcap", "rb")).iter_messages(
            topics=["/perception/latency"])]
        assert (np.percentile(lat, 95) > 100) == (n == "rain_crosswalk"), n
    det = _first(root / "outputs" / "day_parking_lot" / "replay.mcap", "/perception/detections")["detections"][0]
    assert {"class", "score", "bbox_2d", "range_m"} == det.keys()
    trk = _first(root / "outputs" / "day_parking_lot" / "replay.mcap", "/perception/tracks")
    assert {"header", "tracks"} == trk.keys()
    # the harness really runs, and reproduces the committed outputs byte for byte
    ws = tmp_path / "ws"
    shutil.copytree(root, ws)
    r = subprocess.run([sys.executable, "replay/run_replay.py", "--scenario", "day_parking_lot"], cwd=ws, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for f in ("replay.mcap", "replay.gif", "camera.mp4"):
        assert (ws / "outputs" / "day_parking_lot" / f).read_bytes() == (root / "outputs" / "day_parking_lot" / f).read_bytes(), f


def test_image_set_eval(built):
    root = built["image_set_eval"]
    meta = list(csv.DictReader(open(root / "meta.csv")))
    assert list(meta[0]) == ["id", "source", "condition", "timestamp"] and len(meta) == 240
    assert {m["source"] for m in meta} == {"dashcam_a", "dashcam_b", "warehouse_cam"}
    assert {m["condition"] for m in meta} == {"day", "night", "fog"}
    assert not list(root.rglob("FAULTS*"))
    for m in meta:
        assert (root / "images" / m["source"] / f"{m['id']}.jpg").exists()
        lab = json.loads((root / "labels" / f"{m['id']}.json").read_text())
        assert lab["annotations"] and len(lab["annotations"][0]["bbox"]) == 4
        for v in ("det-v4.1", "det-v4.2"):
            assert (root / "predictions" / v / f"{m['id']}.json").exists()
    r = subprocess.run([sys.executable, "eval.py"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "det-v4.1: mAP@0.5" in r.stdout and "det-v4.2: mAP@0.5" in r.stdout
    sys.path.insert(0, str(root))
    try:
        import eval as ev
        a, b = ev.evaluate("det-v4.1"), ev.evaluate("det-v4.2")
    finally:
        sys.path.remove(str(root))
        sys.modules.pop("eval", None)
    assert b["mAP50"] > a["mAP50"] and b["recall"]["forklift"] > a["recall"]["forklift"] + 0.3

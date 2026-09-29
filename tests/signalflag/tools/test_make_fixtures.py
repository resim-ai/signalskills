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

# SignalFlag Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every skill task ALSO requires superpowers:writing-skills — the RED/GREEN/REFACTOR protocol below is that skill applied here.

**Goal:** Nine `signalflag-*` skills in `superflowers/` that get a team's experiments into SignalFlag through the Python SDK, each proven against baseline agent failures.

**Architecture:** One skill per job, linked by a per-test-type brief in the user's repo (`docs/signalflag/<topic>-brief.md`). `onboard` writes the brief and routes; later skills read it and append their section. The two small scripts (`check_token.py`, `login.py`) and the test tooling are ordinary TDD'd Python; skill prose is TDD'd with subagent scenarios.

**Tech Stack:** Markdown skills; Python 3.12; `signalflag==1.8.0` (PyPI, imports `signalflag.sdk`); pytest; numpy, pandas, pyarrow, pillow, pyyaml, mcap for fixtures and tooling.

**Spec:** `docs/superpowers/specs/2026-09-28-signalflag-skills-design.md`. Read it before any task. Where this plan and the spec disagree, the spec wins; flag the disagreement.

## Global Constraints

- SDK only: `pip install signalflag`, `from signalflag.sdk ...`. No `resim`/`signalflag` CLI, no Docker, no cloud runs, no metrics builds — in skills and in tests.
- Auth is `DeviceCodeClient`. No credential files, no username/password.
- MCP: `claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp`.
- Config path `.resim/metrics/config.resim.yml`, templates `.resim/metrics/templates/`.
- App links `https://app.signalflag.ai/projects/<pid>/batches/<bid>`.
- `superflowers/` holds skills only. Tests, scenarios, baselines, fixtures, tooling: `docs/superpowers/skill-tests/signalflag/` (call it `$SKT`).
- Skill names: `signalflag-<verb-or-noun>`, letters/digits/hyphens. Descriptions start "Use when", third person, triggers only, no workflow summary, < 500 chars.
- SKILL.md bodies < 500 words; heavy syntax goes in the skill's reference files.
- Dependencies: separate ingest → dedicated venv + pinned `requirements.txt`, never outside a venv; inside a codebase → that codebase's manager, as an optional extra/dev group where it has one. The same rule governs this plan's own tooling: `$SKT/.venv` only.
- Every metric `skip_if_no_data: true`; 5–20 metrics per page; one-line descriptions; summary video/GIF first when a camera exists.
- The brief never gets a branch or test names the user did not confirm.
- Test pushes go to project `skilltest-project`, branches named `skilltest-<skill>-<yyyymmdd>-<n>`.
- Code style: terse, functional, minimal comments (user memory).

## Review Focus

1. **Corrupt or partial token cache** (a killed login leaves half a JSON file) — `check_token.py` must report missing, not crash. Pinned in Task 1 (`test_corrupt_cache_is_missing`).
2. **A hooked test that falls short of its threshold** — must close SUCCEEDED with the value emitted and the status check deciding, not ERROR with a stacktrace. Pinned in Task 5, scenario I2 (the pytest fixture has one parametrize case that misses its threshold).
3. **More than 100 media files per run** (one PNG per frame) — ingest must aggregate to a GIF/video, not reference each frame. Pinned in Task 5, scenario I3 (the sim fixture writes 150 frames).
4. **A data-first user whose next log has a new field** — long-format topics absorb it with no schema change. Pinned in Task 4, scenario C2 (second parquet generation adds `motor_temp_c`).
5. **Sim time vs receive time in mcaps** — series stamped from log time stretch the run by the RTF. Pinned in Task 5, scenario I1 (the M6 bags; criterion: emitted span within 10% of the bag's header-stamp span).

---

## The scenario protocol (every skill task)

This is superpowers:writing-skills made concrete. Each skill task names its scenarios; this is how every one is run.

**Files per skill** in `$SKT/<skill>/`: `scenarios.md` (prompts, setup, pass criteria — written in the task), `baseline.md` (RED transcripts' key moves and verbatim rationalizations), `green.md` (same for GREEN), `refactor.md` (loopholes found and closed).

**Workspace per run:** `$SKT/work/<scenario>-<rep>/`, created by `$SKT/tools/new_workspace.sh <fixture> <scenario>-<rep>` (Task 0). `$SKT/work/` is gitignored.

**RED:**
1. Ensure `.claude/skills/signalflag-<skill>` does NOT exist (earlier skills stay installed — later baselines are "the set so far, minus this skill").
2. For each scenario, 3 reps: dispatch a fresh `general-purpose` subagent with the scenario prompt verbatim, prefixed with `Work only inside <workspace>. `. Interactive scenarios: the controller plays the persona from `scenarios.md`, replying via SendMessage, in character, never volunteering SignalFlag terms.
3. Score each run against the pass criteria. Record in `baseline.md`: per criterion pass/fail per rep, and the agent's verbatim wording where it went wrong.
4. **If every criterion passes in every rep, the skill is not needed.** Stop, record it, report to the human partner. Do not write it.

**GREEN:**
1. Write the skill against the failures in `baseline.md`, carrying the spec's required content for that skill. Nothing for hypothetical failures.
2. `ln -s ../../superflowers/signalflag-<skill> .claude/skills/signalflag-<skill>`
3. Re-run the same scenarios, 3 reps, fresh subagents. Record in `green.md`.
4. Pass = every criterion in every rep.

**REFACTOR:** each new failure or rationalization → an explicit counter in the skill → re-run the failing scenario 3 reps. Wording that won't bind: micro-test it (5 reps, fresh context, with a no-guidance control) before adding words. Record in `refactor.md`.

**Finish:** `wc -w superflowers/signalflag-<skill>/SKILL.md` < 500; frontmatter per Global Constraints; commit `superflowers/signalflag-<skill>/` and `$SKT/<skill>/`.

---

### Task 0: Test tooling and fixtures

**Files:**
- Create: `$SKT/requirements.txt`, `$SKT/tools/new_workspace.sh`, `$SKT/tools/make_fixtures.py`, `$SKT/tools/test_make_fixtures.py`
- Create (generated, committed): `$SKT/fixtures/{rl_project,pytest_suite,parquet_dump,sim_runner}/`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `bash $SKT/tools/new_workspace.sh <fixture> <name>` → prints the workspace path; fixtures `m6` (this repo's `autonomy/ws/runs/*`, bags symlinked), `replay` (`test-orchestrator/`, outputs symlinked), `rl_project`, `pytest_suite`, `parquet_dump`, `sim_runner`.
- Produces: `$SKT/.venv/bin/python` with the pinned tooling deps.

- [ ] **Step 1: venv and ignores**

`$SKT/requirements.txt`:
```
signalflag==1.8.0
numpy==2.1.3
pandas==2.2.3
pyarrow==18.1.0
pillow==11.0.0
pyyaml==6.0.2
mcap==1.2.1
pytest==8.3.4
```
Append to `.gitignore`:
```
# SignalFlag skill tests: tooling venv and per-run workspaces.
docs/superpowers/skill-tests/signalflag/.venv/
docs/superpowers/skill-tests/signalflag/work/
```
Run: `python3 -m venv $SKT/.venv && $SKT/.venv/bin/pip install -q -r $SKT/requirements.txt && $SKT/.venv/bin/python -c "import signalflag.sdk.batch, mcap, pyarrow; print('ok')"`
Expected: `ok`. If a pin fails to resolve, bump to the nearest available version and note it in the commit.

- [ ] **Step 2: Write the failing fixture tests**

`$SKT/tools/test_make_fixtures.py`:
```python
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
```
Run: `cd $SKT/tools && ../.venv/bin/python -m pytest -q test_make_fixtures.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'make_fixtures'`.

- [ ] **Step 3: Implement the fixture generator**

`$SKT/tools/make_fixtures.py`:
```python
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
```
Run: `cd $SKT/tools && ../.venv/bin/python -m pytest -q test_make_fixtures.py`
Expected: `5 passed`. If `test_pytest_suite_has_one_case_below_threshold` reports a different pass/fail split, adjust the `clutter` obstacles until exactly one case fails `min_clearance_m > 0.25`; the point is one real shortfall.

- [ ] **Step 4: Generate the committed fixtures**

Run: `cd $SKT/tools && ../.venv/bin/python make_fixtures.py ../fixtures && rm -rf ../fixtures/sim_runner/runs`
Expected: four paths printed; `sim_runner` committed without runs (scenarios generate them).

- [ ] **Step 5: Workspace script**

`$SKT/tools/new_workspace.sh`:
```bash
#!/usr/bin/env bash
# new_workspace.sh <fixture> <name> -> prints a fresh workspace under $SKT/work/
set -euo pipefail
skt="$(cd "$(dirname "$0")/.." && pwd)"
repo="$(git -C "$skt" rev-parse --show-toplevel)"
ws="$skt/work/$2"
rm -rf "$ws" && mkdir -p "$ws"
case "$1" in
  m6)
    for run in "$repo"/autonomy/ws/runs/*/; do
      name="$(basename "$run")"; mkdir -p "$ws/runs/$name"
      cp -r "$run/results.json" "$run/logs" "$ws/runs/$name/"
      [ -f "$run/replay.gif" ] && cp "$run/replay.gif" "$ws/runs/$name/"
      [ -d "$run/bag" ] && ln -s "$run/bag" "$ws/runs/$name/bag"
    done ;;
  replay)
    cp -r "$repo/test-orchestrator/"{README.md,compose.yaml,orchestrator,scenarios,schema,test-creator} "$ws/"
    ln -s "$repo/test-orchestrator/outputs" "$ws/outputs"
    ln -s "$repo/test-orchestrator/experiences" "$ws/experiences" ;;
  *) cp -r "$skt/fixtures/$1/." "$ws/" ;;
esac
git -C "$ws" init -q && git -C "$ws" add -A && git -C "$ws" commit -qm fixture
echo "$ws"
```
Run: `bash $SKT/tools/new_workspace.sh m6 smoke && ls $SKT/work/smoke/runs && bash $SKT/tools/new_workspace.sh rl_project smoke2 && ls $SKT/work/smoke2`
Expected: three M6 run names; `eval_checkpoint.py evals tests`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore docs/superpowers/skill-tests/signalflag/{requirements.txt,tools,fixtures}
git commit -m "Skill tests: tooling venv, fixtures, workspaces for the SignalFlag skills"
```

---

### Task 1: signalflag-auth

**Files:**
- Create: `superflowers/signalflag-auth/SKILL.md`, `superflowers/signalflag-auth/scripts/check_token.py`, `superflowers/signalflag-auth/scripts/login.py`
- Test: `$SKT/auth/test_check_token.py`, `$SKT/auth/test_login.py`, `$SKT/auth/scenarios.md`

**Interfaces:**
- Produces: `python <skill>/scripts/check_token.py` → exit 0 valid / 1 expired / 2 missing, one line on stdout (`valid until <iso>`, `expired: <path>`, `missing: no token at <path>`). No third-party imports.
- Produces: `<venv>/bin/python <skill>/scripts/login.py` → prints the notice, runs `DeviceCodeClient()`, exit 0; exit 3 if `signalflag` isn't importable.
- Produces: the rule every API-calling skill follows: "Run signalflag-auth first."

- [ ] **Step 1: Write the failing script tests**

`$SKT/auth/test_check_token.py`:
```python
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[5] / "superflowers/signalflag-auth/scripts"))
import check_token as ct

NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def put(home: Path, d: str, body: str) -> None:
    (home / d).mkdir(parents=True, exist_ok=True)
    (home / d / "token.json").write_text(body)


def tok(delta: timedelta) -> str:
    return json.dumps({"access_token": "x", "expires_at": (NOW + delta).isoformat()})


def test_valid(tmp_path):
    put(tmp_path, ".signalflag", tok(timedelta(hours=5)))
    assert ct.status(tmp_path, NOW)[0] == 0


def test_inside_one_hour_margin_is_expired(tmp_path):
    put(tmp_path, ".signalflag", tok(timedelta(minutes=30)))
    assert ct.status(tmp_path, NOW)[0] == 1


def test_no_expires_at_is_expired(tmp_path):
    put(tmp_path, ".signalflag", json.dumps({"access_token": "x"}))
    assert ct.status(tmp_path, NOW)[0] == 1


def test_missing(tmp_path):
    code, msg = ct.status(tmp_path, NOW)
    assert code == 2 and ".signalflag/token.json" in msg


def test_corrupt_cache_is_missing(tmp_path):
    put(tmp_path, ".signalflag", '{"access_tok')
    assert ct.status(tmp_path, NOW)[0] == 2


def test_legacy_dir_used_when_only_it_exists(tmp_path):
    put(tmp_path, ".resim", tok(timedelta(hours=5)))
    assert ct.status(tmp_path, NOW)[0] == 0


def test_signalflag_dir_wins_over_legacy(tmp_path):
    put(tmp_path, ".resim", tok(timedelta(hours=5)))
    (tmp_path / ".signalflag").mkdir()
    assert ct.status(tmp_path, NOW)[0] == 2
```
`$SKT/auth/test_login.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[5] / "superflowers/signalflag-auth/scripts"))
import login


def test_notice_before_client(capsys):
    seen = []
    def fake():
        seen.append(capsys.readouterr().out)
    assert login.main(make_client=fake) == 0
    assert "URL" in seen[0]


def test_missing_sdk_exits_3(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "signalflag.sdk.auth", None)
    assert login.main() == 3
    assert "venv" in capsys.readouterr().err
```
Run: `$SKT/.venv/bin/python -m pytest -q $SKT/auth`
Expected: FAIL, `ModuleNotFoundError: No module named 'check_token'`.

- [ ] **Step 2: Implement the scripts**

`superflowers/signalflag-auth/scripts/check_token.py`:
```python
"""Is there a usable SignalFlag token? Exit 0 valid, 1 expired, 2 missing. Stdlib only."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARGIN = timedelta(hours=1)  # the SDK refreshes inside this window


def cache_path(home: Path) -> Path:
    current, legacy = home / ".signalflag", home / ".resim"
    if not current.exists() and legacy.is_dir():
        return legacy / "token.json"
    return current / "token.json"


def status(home: Path, now: datetime) -> tuple[int, str]:
    path = cache_path(home)
    try:
        token = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return 2, f"missing: no token at {path}"
    expires = token.get("expires_at")
    if not expires or now + MARGIN > datetime.fromisoformat(expires):
        return 1, f"expired: {path}"
    return 0, f"valid until {expires}"


if __name__ == "__main__":
    code, msg = status(Path.home(), datetime.now(timezone.utc))
    print(msg)
    sys.exit(code)
```
`superflowers/signalflag-auth/scripts/login.py`:
```python
"""Log in to SignalFlag (device code flow). The SDK reuses the cached token after this."""
import sys

NOTICE = ("SignalFlag login: a URL will print below. Open it in a browser and approve; "
          "this finishes by itself. The token is cached in ~/.signalflag/token.json.")


def main(make_client=None) -> int:
    print(NOTICE, flush=True)
    if make_client is None:
        try:
            from signalflag.sdk.auth import DeviceCodeClient
        except ImportError:
            print("signalflag is not installed in this Python. Run login.py with the venv's "
                  "python: <venv>/bin/python login.py", file=sys.stderr)
            return 3
        make_client = DeviceCodeClient
    make_client()
    print("Logged in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
Run: `$SKT/.venv/bin/python -m pytest -q $SKT/auth`
Expected: `9 passed`.

- [ ] **Step 3: Commit the scripts**

```bash
git add superflowers/signalflag-auth/scripts docs/superpowers/skill-tests/signalflag/auth/test_*.py
git commit -m "signalflag-auth: token check and device-code login scripts"
```

- [ ] **Step 4: Write `$SKT/auth/scenarios.md`**

```markdown
# signalflag-auth scenarios

Setup for all: the M6 workspace, with the prompt prefix "Run every shell command with `HOME=<ws>/home` set." so the real token cache is untouched.

## A1 — no token, push requested
Setup: empty HOME. `$SKT/.venv` exists and has signalflag.
Prompt: "Push the three runs in runs/ to SignalFlag, project skilltest-project, branch skilltest-auth-<date>-1. Just get them up."
Stop the run once the agent's next action would be an upload.
Pass:
- Checks for a token before any API call.
- Tells the user a login URL is coming and what to do with it, before it appears.
- Asks the user to run the login script (as `! <venv>/bin/python .../login.py`), rather than running the device flow in its own foreground shell where the URL is never seen.
- Does not ask for a username, password, client secret or credential file; does not use the CLI.
- Installs nothing outside a venv.

## A2 — valid token
Setup: HOME with a valid `.signalflag/token.json` (expires in 5 h).
Same prompt.
Pass: proceeds without prompting a login; does not delete or rewrite the cache.

## A3 — MCP not connected
Setup: valid token. Prompt: "Check what the last batch on skilltest-auth-<date>-1 shows."
Pass: detects the `signalflag` MCP isn't connected; gives `claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp` and `/mcp` to authenticate; does not try the CLI or scrape the web app.
```

- [ ] **Step 5: RED** — protocol RED on A1–A3. Expect failures like: running `DeviceCodeClient()` in a blocking foreground shell, reaching for `.resim_cred`/`UsernamePasswordClient` because the still-installed `/resim-run` prescribes it, suggesting the CLI.

- [ ] **Step 6: GREEN** — write `superflowers/signalflag-auth/SKILL.md`. Required content: when it runs (first, in every API-calling skill); `check_token.py` and its three outcomes; the venv to use (the brief's named environment; if none, create `.venv-signalflag/` with `pip install signalflag==1.8.0` and gitignore it); the notice-then-`! <venv>/bin/python <skill>/scripts/login.py` handoff; MCP check and the `claude mcp add` line; the legacy `~/.resim/` fallback in one line. Then protocol GREEN.

- [ ] **Step 7: REFACTOR and finish** — protocol REFACTOR, then Finish. Commit: `git commit -m "signalflag-auth: skill, proven against baseline"`.

- [ ] **Step 8: Real login, once** — ask the human partner to run `! $SKT/.venv/bin/python superflowers/signalflag-auth/scripts/login.py` and connect the MCP with the `claude mcp add` line. Later tasks push for real. Record the MCP's tool list (`/mcp` or the tools that appear) in `$SKT/verify/mcp-tools.md`; Task 7 builds on it.

---

### Task 2: signalflag-sdk-onboard (+ the signalflag-model decision)

**Files:**
- Create: `superflowers/signalflag-sdk-onboard/SKILL.md`, `superflowers/signalflag-sdk-onboard/brief-template.md`
- Create if earned: `superflowers/signalflag-model/SKILL.md`
- Test: `$SKT/onboard/scenarios.md`; approved briefs copied to `$SKT/fixtures/briefs/<scenario>.md` for Tasks 3–8

**Interfaces:**
- Consumes: signalflag-auth (named as a next skill, not run — onboard makes no API calls).
- Produces: `docs/signalflag/<topic>-brief.md` in the user's repo with sections, in order: `## Current state`, `## Intent`, `## Control`, `## Mapping`, `## Integration`, `## Data profile`, `## Metrics plan`, `## Config`, `## Verification`. Onboard fills the first five; later ones are headed and left `_pending: <owning skill>_`.
- Produces: a closing "Next skills:" line naming skills in order.

- [ ] **Step 1: Write `brief-template.md`** — the nine headings above, each with a one-line italic note of what goes there (from the spec's brief table) and who owns it. Under Mapping: `Project:`, `Branch:` (+ `confirmed by user: yes/no`), `Batch is:`, `Test is:` (+ confirmed), `Version is:`. Under Integration: `Form: harness | hook | script | one-off`, `structure-runs needed: yes/no — why`, `Environment:` (venv path or the codebase's manager).

- [ ] **Step 2: Write `$SKT/onboard/scenarios.md`**

```markdown
# signalflag-sdk-onboard scenarios

Controller plays the persona. Answer only what is asked, in the persona's words; if asked in SignalFlag vocabulary you don't understand as the persona, say so ("what's an experience?").

## O1 — M6 sweep, CI-style regression (workspace m6)
Persona: controls engineer. "I change the path tracker and rerun these three routes. I want to know if I made it worse." Branch they'd accept: `m6-eval`. Tests are the route names.
Prompt: "I want these runs in SignalFlag."

## O2 — RL checkpoints, leaderboard over training (workspace rl_project)
Persona: RL researcher. Evaluates each checkpoint as training runs; wants a ranking of checkpoints by mean return and success rate, and a trend. Doesn't know what a batch is.
Prompt: "Can you hook my checkpoint evals up to SignalFlag?"

## O3 — local pytest harness (workspace pytest_suite)
Persona: planning engineer. Runs `pytest` locally and in CI on every PR; wants failures visible with the numbers behind them.
Prompt: "Get my planner tests reporting to SignalFlag."

## O4 — data-first telemetry dump (workspace parquet_dump)
Persona: field engineer. "I don't know what I'll ask yet. I want it all queryable." Agent-led control.
Prompt: "Put our drive telemetry in SignalFlag."

## O5 — perception replay harness (workspace replay)
Persona: perception engineer. The replay harness produces output bags per scenario; grading comes later and separately.
Prompt: "Wire SignalFlag into the replay harness."

Pass (every scenario):
- Reads existing tests/harness/runner code before the first question; the first question is grounded in a concrete run or file it found.
- One question per message; each carries a best guess.
- No SignalFlag vocabulary in a question before the user has been shown what it means with their own data.
- Branch and test names are confirmed by the user, never silently chosen; test names are never invented to enable A/B comparison.
- Brief written to `docs/signalflag/<topic>-brief.md` with all nine headings; first five filled.
- Integration form: O1 script, O2 script (+ structure-runs: yes, eval folders lack the checkpoint step), O3 hook with the dependency as the pyproject extra, O4 one-off or script, O5 harness.
- Intent: O4 recorded data-first; others metrics-first.
- O2 shape: batch per evaluation cycle on one branch + dashboard (evaluated as training runs).
- Ends with "Next skills:" in dependency order, skipping unneeded ones.
- No API calls, no installs.

Model-question scoring (from RED only), per rep, O1–O3: did it (a) invent test names, (b) plan one dashboard's data across branches, (c) force a leaderboard into A/B comparison? Record counts.
```

- [ ] **Step 3: RED** — protocol RED, O1–O5.

- [ ] **Step 4: Decide signalflag-model** — if the model-question counts are all zero, no model skill: fold the comparison rules (spec §signalflag-model) into onboard's Mapping guidance and record the decision in `$SKT/onboard/baseline.md`. Otherwise write `superflowers/signalflag-model/SKILL.md` from the observed mis-mappings (project, branch, batch, test, experience, version, metrics set, dashboard; same-named pairing; dashboards and reports read one branch) and have onboard reference it as `**REQUIRED BACKGROUND:** signalflag-model`. Either way, tell the human partner which and why, with the counts.

- [ ] **Step 5: GREEN** — write `superflowers/signalflag-sdk-onboard/SKILL.md` against the RED failures. Required content from the spec: read order (harness → runner → artifacts → user) and the harness-to-SignalFlag table; interview from a concrete run; intent (metrics-first / data-first); shape table incl. the RL split; integration table incl. "structure-runs only if"; control levels; never-guess rule; one brief per test type; done condition and next-skills routing. Protocol GREEN. Copy each GREEN rep-1 brief to `$SKT/fixtures/briefs/o<n>.md`.

- [ ] **Step 6: REFACTOR and finish** — protocol REFACTOR, Finish. Commit: `git commit -m "signalflag-sdk-onboard: skill and brief template, proven against baseline"`.

---

### Task 3: signalflag-design-metrics

**Files:**
- Create: `superflowers/signalflag-design-metrics/SKILL.md`, `superflowers/signalflag-design-metrics/catalog.md`
- Test: `$SKT/design-metrics/scenarios.md`; resulting briefs to `$SKT/fixtures/briefs/d<n>.md`

**Interfaces:**
- Consumes: a brief with the first five sections filled (`$SKT/fixtures/briefs/o1.md`, `o2.md`, `o4.md`).
- Produces: the brief's `## Data profile` and `## Metrics plan`. Metrics plan is a table with columns exactly `Question | Metric | Level | Template | Status check | Units | Threshold source | Description`, plus an `### Events` table `Event | Trigger | Backing metric | Auto/User`.

- [ ] **Step 1: Write `catalog.md`** — starter metrics per domain (navigation, manipulation, perception, RL training/evaluation, sim health), each row `Metric | Needs (fields) | Level | Template`. Only metrics whose "Needs" column names concrete fields; the skill proposes a row only when the data profile has those fields.

- [ ] **Step 2: Write `$SKT/design-metrics/scenarios.md`**

```markdown
# signalflag-design-metrics scenarios

## D1 — agent-led, M6 (workspace m6, brief o1.md at docs/signalflag/)
Prompt: "The brief is approved. Design the metrics — your call, I'll look at the result."
## D2 — partial, RL (workspace rl_project, brief o2.md)
Persona: wants to pick from options. Picks mean return, success rate, and "whatever shows variance across seeds".
Prompt: "Next step on the brief: metrics. Give me options."
## D3 — user-led with an unsupported ask (workspace parquet_dump, brief o4.md)
Persona dictates: speed tracking error over time, battery drain rate, and "time spent in obstacle avoidance mode".
Prompt: "Here's what I want charted: ..." (the three above)

Pass:
- Data profile written from reading the data, not from the brief alone.
- D1/D2: a camera/replay GIF exists → a summary GIF/video metric is first on the test page.
- Test-page metric count 5–20 in each plan; related headline scalars grouped into a table, not a row of scalars.
- D1: at least four distinct templates.
- Every metric traces to a Question in the brief; every metric has units and a one-line description.
- A margin metric (distance to threshold) alongside any pass/fail.
- Every threshold has a source.
- D2 leaderboard is a table or bar at batch or dashboard level, sorted by the user's metric.
- Events table includes the auto events the plan implies (threshold crossings; state changes where a state series exists — D3 `mode`; harness failures).
- D3: flags that "obstacle avoidance mode" isn't in the data (only AUTO/IDLE) instead of fabricating it.
- Emit-wide stated: everything readable is planned for emission even when not charted.
- A metric no system template can draw is routed to a custom template, not dropped or distorted.
```

- [ ] **Step 3: RED** — protocol RED, D1–D3.

- [ ] **Step 4: GREEN** — write the SKILL.md. Required content from the spec: control-level table; data profile first; the three levels; question → chart table; the eleven disciplines; auto events + user events; `catalog.md` use rule. Protocol GREEN. Copy GREEN rep-1 briefs to `$SKT/fixtures/briefs/d<n>.md`.

- [ ] **Step 5: REFACTOR and finish** — protocol REFACTOR, Finish. Commit: `git commit -m "signalflag-design-metrics: skill and catalog, proven against baseline"`.

---

### Task 4: signalflag-compose-metrics

**Files:**
- Create: `superflowers/signalflag-compose-metrics/SKILL.md`, `.../config-reference.md`, `.../templates.md`
- Create: `$SKT/tools/check_config.py`, `$SKT/tools/test_check_config.py`, `$SKT/tools/sync_check.py`
- Test: `$SKT/compose-metrics/scenarios.md`

**Interfaces:**
- Consumes: a brief with the Metrics plan (`$SKT/fixtures/briefs/d1.md`, `d3.md`).
- Produces: `.resim/metrics/config.resim.yml` (+ `templates/*.liquid`), the brief's `## Config` (topics list, metrics set name, config path).
- Produces (tooling): `check_config.py <config>` → one violation per line, exit 1 if any. `sync_check.py <config> <branch>` → syncs to `skilltest-project` via `signalflag.sdk.bff_client.metrics.sync_config`, exit 0 on acceptance.

- [ ] **Step 1: Write the failing checker tests**

`$SKT/tools/test_check_config.py`:
```python
import textwrap
from pathlib import Path
import check_config as cc

GOOD = """
version: 1
topics:
  replay: {schema: {filename: video}}
  err: {schema: {t: float, err_m: float}}
  moment: {event: true, schema: {name: string, description: string, status: status, tags: "string[]", metrics: "metric[]"}}
metrics:
  Replay: {type: test, query_string: SELECT filename AS value FROM replay, template_type: system, template: video, skip_if_no_data: true, description: What ran.}
  Error: {type: test, query_string: "SELECT 'e' AS series, t, err_m FROM err", template_type: system, template: line, skip_if_no_data: true, description: Error over time (m).}
  Peak: {type: test, query_string: SELECT MAX(err_m) AS value FROM err, template_type: system, template: scalar, units: m, skip_if_no_data: true, description: Worst error.}
  A: {type: test, query_string: SELECT 1, template_type: system, template: table, skip_if_no_data: true, description: a.}
  B: {type: test, query_string: SELECT 1, template_type: system, template: histogram, skip_if_no_data: true, description: b.}
metrics sets:
  S: {metrics: [Replay, Error, Peak, A, B]}
"""


def check(tmp_path, text, **kw):
    p = tmp_path / "config.resim.yml"
    p.write_text(textwrap.dedent(text))
    return cc.violations(p, **kw)


def test_good_config_is_clean(tmp_path):
    assert check(tmp_path, GOOD) == []


def test_missing_skip_if_no_data(tmp_path):
    assert any("skip_if_no_data" in v for v in check(tmp_path, GOOD.replace("skip_if_no_data: true, description: b.", "description: b.")))


def test_unknown_template(tmp_path):
    assert any("bar_chart" in v for v in check(tmp_path, GOOD.replace("template: histogram", "template: bar_chart")))


def test_unknown_topic_type(tmp_path):
    assert any("double" in v for v in check(tmp_path, GOOD.replace("t: float", "t: double")))


def test_event_topic_needs_event_schema(tmp_path):
    assert any("moment" in v for v in check(tmp_path, GOOD.replace("status: status, ", "")))


def test_too_few_test_metrics(tmp_path):
    assert any("5-20" in v for v in check(tmp_path, GOOD.replace("[Replay, Error, Peak, A, B]", "[Replay, Error]")))


def test_video_must_lead_when_present(tmp_path):
    assert any("first" in v for v in check(tmp_path, GOOD.replace("[Replay, Error, Peak, A, B]", "[Error, Replay, Peak, A, B]")))


def test_scalar_needs_units(tmp_path):
    assert any("units" in v for v in check(tmp_path, GOOD.replace("units: m, ", "")))


def test_long_description(tmp_path):
    assert any("description" in v for v in check(tmp_path, GOOD.replace("description: a.", "description: " + "x" * 200)))


def test_set_references_unknown_metric(tmp_path):
    assert any("Nope" in v for v in check(tmp_path, GOOD.replace("B]", "Nope]")))


def test_custom_template_file_must_exist(tmp_path):
    text = GOOD.replace("template_type: system, template: table", "template_type: custom, template_file: raw.liquid")
    assert any("raw.liquid" in v for v in check(tmp_path, text))
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "raw.liquid").write_text("")
    assert check(tmp_path, text) == []
```
Run: `cd $SKT/tools && ../.venv/bin/python -m pytest -q test_check_config.py`
Expected: FAIL, `No module named 'check_config'`.

- [ ] **Step 2: Implement the checker and the sync check**

`$SKT/tools/check_config.py`:
```python
"""Static checks of a config.resim.yml against the SignalFlag skill rules. Exit 1 on any violation."""
import sys
from pathlib import Path
import yaml

SYSTEM_TEMPLATES = {"line", "bar", "table", "scalar", "state_timeline", "histogram", "pie", "image", "video", "artifact"}
TOPIC_TYPES = {"boolean", "int", "float", "string", "status", "image", "video", "string[]", "metric[]"}
EVENT_FIELDS = {"name", "description", "status", "tags"}
MEDIA = {"image", "video"}
MAX_DESCRIPTION = 120


def _topic_violations(topics: dict) -> list[str]:
    out = []
    for name, t in topics.items():
        schema = t.get("schema", {})
        out += [f"topic {name}: unknown type {ty!r} for {col}" for col, ty in schema.items() if ty not in TOPIC_TYPES]
        if t.get("event") and not EVENT_FIELDS <= schema.keys():
            out.append(f"topic {name}: event schema needs {sorted(EVENT_FIELDS)}")
    return out


def _metric_violations(metrics: dict, templates_dir: Path) -> list[str]:
    out = []
    for name, m in metrics.items():
        if m.get("skip_if_no_data") is not True:
            out.append(f"metric {name}: skip_if_no_data must be true")
        d = str(m.get("description", ""))
        if not d or "\n" in d.strip() or len(d) > MAX_DESCRIPTION:
            out.append(f"metric {name}: description must be one line, <= {MAX_DESCRIPTION} chars")
        if m.get("template_type") == "custom":
            f = m.get("template_file")
            if not f or not (templates_dir / f).exists():
                out.append(f"metric {name}: custom template {f} not found in {templates_dir}")
        elif m.get("template") not in SYSTEM_TEMPLATES:
            out.append(f"metric {name}: unknown template {m.get('template')!r}")
        if m.get("template") == "scalar" and not m.get("units"):
            out.append(f"metric {name}: scalar needs units")
    return out


def _set_violations(sets: dict, metrics: dict) -> list[str]:
    out = []
    for sname, s in sets.items():
        names = s.get("metrics", [])
        out += [f"set {sname}: unknown metric {n}" for n in names if n not in metrics]
        test = [n for n in names if metrics.get(n, {}).get("type") == "test"]
        if not 5 <= len(test) <= 20:
            out.append(f"set {sname}: {len(test)} test metrics, want 5-20")
        media = [n for n in test if metrics[n].get("template") in MEDIA]
        if media and test[0] not in media:
            out.append(f"set {sname}: media metric {media[0]} must come first")
        for level in ("batch", "dashboard"):
            if sum(metrics.get(n, {}).get("type") == level for n in names) > 20:
                out.append(f"set {sname}: more than 20 {level} metrics")
    return out


def violations(path: Path) -> list[str]:
    cfg = yaml.safe_load(path.read_text())
    metrics = cfg.get("metrics", {})
    return (_topic_violations(cfg.get("topics", {}))
            + _metric_violations(metrics, path.parent / "templates")
            + _set_violations(cfg.get("metrics sets", {}), metrics))


if __name__ == "__main__":
    found = violations(Path(sys.argv[1]))
    print("\n".join(found) or "clean")
    sys.exit(1 if found else 0)
```
`$SKT/tools/sync_check.py`:
```python
"""Sync a config to skilltest-project on <branch>; exit 0 if SignalFlag accepts it. `sync_check.py <config> <branch>`."""
import sys
from pathlib import Path
from signalflag.sdk.auth import DeviceCodeClient
from signalflag.sdk.bff_client import metrics
from signalflag.sdk.client.api.projects import list_projects

PROJECT = "skilltest-project"


def project_id(client) -> str:
    return next(str(p.project_id) for p in list_projects.sync(client=client).projects if p.name == PROJECT)


if __name__ == "__main__":
    config = Path(sys.argv[1])
    client = DeviceCodeClient()
    metrics.sync_config(client, project_id(client), sys.argv[2], config_path=str(config),
                        templates_path=str(config.parent / "templates"))
    print("accepted")
```
Run: `cd $SKT/tools && ../.venv/bin/python -m pytest -q test_check_config.py`
Expected: `11 passed`.
Run: `$SKT/.venv/bin/python $SKT/tools/check_config.py $SKT/.venv/lib/python3.12/site-packages/signalflag/demo/data/config.resim.yml`
Expected: some violations (the demo doesn't follow our rules, e.g. missing `skip_if_no_data`) and no crash. That proves the checker reads real configs.
Run: `$SKT/.venv/bin/python $SKT/tools/sync_check.py $SKT/.venv/lib/python3.12/site-packages/signalflag/demo/data/config.resim.yml skilltest-compose-$(date +%Y%m%d)-0`
Expected: `accepted` (the demo config is known-good; this proves the sync path). If `list_projects.sync` pages past the project, add paging as in `Batch.__resolve_project_id`.

- [ ] **Step 3: Commit tooling**

```bash
git add docs/superpowers/skill-tests/signalflag/tools/{check_config.py,test_check_config.py,sync_check.py}
git commit -m "Skill tests: static config checker and a SignalFlag sync check"
```

- [ ] **Step 4: Write `$SKT/compose-metrics/scenarios.md`**

```markdown
# signalflag-compose-metrics scenarios

## C1 — metrics-first, M6 (workspace m6, brief d1.md)
Prompt: "Write the SignalFlag config for this brief."
## C2 — data-first, parquet (workspace parquet_dump, brief d3.md)
Prompt: "Write the config." Then, after it finishes: "We just got telemetry_v2/ — it has a new field. Update whatever needs updating."
## C3 — escape hatch (workspace m6, brief d1.md with an added plan row: "Per-route cross-track error as a box plot with every sample shown" at batch level)
Prompt: "Write the config."

Pass:
- `check_config.py` clean on the result.
- `sync_check.py <config> skilltest-compose-<date>-<n>` prints `accepted`.
- Every Metrics-plan row is a metric; nothing charted that isn't in the plan.
- Event topics use `event: true` with the conventional schema.
- C2: topics long-format enough that `motor_temp_c` needs no topic/column change — zero schema edits after the second prompt (a new metric is fine).
- C3: a custom Liquid template or emitted Plotly `raw_metric` — not a distorted system chart.
- The brief's `## Config` filled.
- No CLI use.
```

- [ ] **Step 5: RED** — protocol RED, C1–C3. Score the tool-checkable criteria with the two tools; read every flagged line.

- [ ] **Step 6: GREEN** — write SKILL.md (short: inputs, outputs, order of work, traps, pointers), `config-reference.md` (topics and types, event schema and `metric[]` object shape, metric fields incl. `skip_if_no_data`, `template_settings`, status checks with `?`, `metadata` columns, SQL dialect, metrics sets, multi-file merge, the additive-only and no-line-number traps), `templates.md` (each system template's column contract with one working query from the demo configs, plus both escape hatches with the `raw.liquid` and `strip.liquid` patterns). Verify every syntax claim against `signalflag/demo/data/*.resim.yml` in the venv or https://docs.signalflag.ai/guides/metrics/ before writing it. Protocol GREEN.

- [ ] **Step 7: REFACTOR and finish** — protocol REFACTOR, Finish. Commit: `git commit -m "signalflag-compose-metrics: skill and references, proven against baseline"`.

---

### Task 5: signalflag-ingest

**Files:**
- Create: `superflowers/signalflag-ingest/SKILL.md`, `.../events.md`, `.../readers/{mcap,parquet,csv,h5,dataframe}.md`
- Test: `$SKT/ingest/scenarios.md`

**Interfaces:**
- Consumes: briefs with Config filled; configs from Task 4's GREEN runs (copy each to the scenario workspace's `.resim/metrics/`).
- Produces (in the user's repo, per mode): reader module(s) with no `signalflag` import; an uploader; a CLI with `--max-tests N --stride K --no-media --branch B` (summary GIF kept under `--no-media`). Verify and iterate call it with these flags.

- [ ] **Step 0: Prepare the I2/I3 inputs** — with onboard, design-metrics and compose-metrics installed, one subagent per workspace (`pytest_suite` with the O3 persona, `sim_runner` with persona "controls engineer tuning `--gain`; wants to see each suite run") runs the three skills end to end, controller answering in persona. Save the brief to `$SKT/fixtures/briefs/{pytest,sim}.md` and the config to `$SKT/fixtures/configs/{pytest,sim}/config.resim.yml` (+ templates). `check_config.py` must be clean on both. Commit them.

- [ ] **Step 1: Write `$SKT/ingest/scenarios.md`**

```markdown
# signalflag-ingest scenarios

All: a valid token in HOME (from Task 1 step 8). Pushes go to `skilltest-ingest-<date>-<n>`.

## I1 — script mode over mcaps (workspace m6, brief + config from C1)
Prompt: "Build the ingest from the brief and push the three runs."
## I2 — hook mode (workspace pytest_suite, `fixtures/briefs/pytest.md` + its config)
Prompt: "Make my pytest run report to SignalFlag."
Then run `pytest` in the workspace with the dev extra installed.
## I3 — harness mode, 150 frames per run (workspace sim_runner, `fixtures/briefs/sim.md` + its config)
Prompt: "Wire SignalFlag into run_suite.py so every suite run reports."
## I4 — one-off (workspace parquet_dump, brief d3 + C2 config)
Prompt: "Just push the telemetry once."

Pass:
- Reader modules never import signalflag (`grep -L signalflag` over them); the uploader never parses files.
- Low-res flags exist and work: `--max-tests 1 --stride 10 --no-media` pushes one test with the summary GIF only.
- Dependencies: I1/I3/I4 in a dedicated venv with a pinned `requirements.txt`; I2 as the pyproject `dev` (or a new `signalflag`) extra. Nothing installed outside a venv (read the transcript's install commands).
- DeviceCodeClient after check_token; no credential files.
- I1: series stamped from header (sim) time: each test's emitted time span is within 10% of its bag's header-stamp span, not its log-time span; the basis is stated in the brief.
- I2: the below-threshold case closes SUCCEEDED with its value emitted; nothing escapes `with Test(...)` except real exceptions.
- I3: frames aggregated into one GIF/video per run; ≤ 100 referenced media files per run.
- Media `filename` in emits equals the attach_log basename.
- Raw artifacts attached per the brief.
- No `emissions_*.resim.jsonl` left in the workspace root.
- Auto events from the plan are emitted with `emit_event` and a single timestamp.
- The push succeeds: batch link printed, every job closed, no LogUploadError.
```

- [ ] **Step 2: RED** — protocol RED, I1–I4.

- [ ] **Step 3: GREEN** — write SKILL.md (reader/uploader split with the two-line signature sketch; mode table; low-res flags; the rules list from the spec incl. dependencies; the `Batch`/`Test` skeleton, verified against `signalflag/sdk/{batch,test}.py` in the venv), `events.md` (detector as `rows -> list[Event]`, `emit_event(topic, data, timestamp)`, backing `metrics` entries `{name, type, value, status?}` with media values as attached filenames), and one reader file per format (how to get rows, columns → `emit_series`, format traps; mcap: header vs log time, `mcap` + decoder choice for ROS 2 CDR). Protocol GREEN.

- [ ] **Step 4: REFACTOR and finish** — protocol REFACTOR, Finish. Commit: `git commit -m "signalflag-ingest: skill, events, readers, proven against baseline"`.

---

### Task 6: signalflag-structure-runs

**Files:**
- Create: `superflowers/signalflag-structure-runs/SKILL.md`
- Test: `$SKT/structure-runs/scenarios.md`

**Interfaces:**
- Consumes: brief o2 (Integration says structure-runs needed: eval folders lack checkpoint step).
- Produces: `run.json` per run folder with the brief's fields; one `write_manifest(run_dir, **fields)` in the runner; a skipped-runs list.

- [ ] **Step 1: Write `$SKT/structure-runs/scenarios.md`**

```markdown
# signalflag-structure-runs scenarios

## S1 — RL eval folders (workspace rl_project, brief o2.md)
Prompt: "The brief says the eval folders are missing what ingest needs. Fix that."

Pass:
- `eval_checkpoint.py` gains one `write_manifest(...)` call where `ckpt` is known; no other restructuring (`git diff --stat` touches the runner plus at most one new helper module).
- `pytest tests` in the workspace still passes.
- A new eval run writes `run.json` with checkpoint step, seeds, time basis, start time.
- Three old folders backfilled from `log.txt`; the 30000 folder reported as skipped, not guessed.
- No dependency added.
```

- [ ] **Step 2: RED**, **Step 3: GREEN** (required content: only-when rule; manifest fields come from the brief; the one-call change; the runner's tests must pass; backfill-or-list), **Step 4: REFACTOR and finish** — per protocol. Commit: `git commit -m "signalflag-structure-runs: skill, proven against baseline"`.

---

### Task 7: signalflag-verify

**Files:**
- Create: `superflowers/signalflag-verify/SKILL.md`
- Test: `$SKT/verify/scenarios.md`, `$SKT/verify/mcp-tools.md` (from Task 1 step 8)

**Interfaces:**
- Consumes: an ingest with low-res flags (Task 5 GREEN workspaces I1, I4), the brief, the MCP tools listed in `mcp-tools.md`.
- Produces: the brief's `## Verification` with low- and high-res results; the batch links.

- [ ] **Step 1: Read the MCP** — from `mcp-tools.md`, find the tools that list batches/jobs, return metric results or statuses, and run queries. Try each against a batch from Task 5 and record in `mcp-tools.md` what each returns. If none returns per-metric data or status, stop and tell the human partner: the high-res value check then relies on local recomputation only, and verify says so.

- [ ] **Step 2: Write `$SKT/verify/scenarios.md`**

```markdown
# signalflag-verify scenarios

## V1 — M6 (the I1 GREEN workspace)
Prompt: "Verify the SignalFlag setup against the brief."
## V2 — planted fault (I4 workspace with the reader's `speed_mps` column silently scaled by 3.6)
Prompt: same.

Pass:
- Low-res first, on a scratch branch (`skilltest-verify-...-scratch` or similar), via the ingest's low-res flags; high-res only after low-res passes, on the brief's branch.
- Low-res checks reported: config synced, emits validated, jobs SUCCEEDED, no LogUploadError, every metric in the set has data via the MCP, statuses as the brief expects.
- Batch link handed to the user after low-res.
- High-res: test and event counts vs source; metric values spot-checked against local recomputation from the reader rows.
- V2: the scaled column is caught (spot-check mismatch) and fixed in the reader, not by a new branch or a config edit.
- Results written to the brief's `## Verification`.
```

- [ ] **Step 3: RED**, **Step 4: GREEN** (required content: the two passes and their checks; the MCP calls by their real names from `mcp-tools.md`; fix-at-cause rule; results into the brief), **Step 5: REFACTOR and finish** — per protocol. Commit: `git commit -m "signalflag-verify: skill, proven against baseline"`.

---

### Task 8: signalflag-iterate

**Files:**
- Create: `superflowers/signalflag-iterate/SKILL.md`
- Test: `$SKT/iterate/scenarios.md`

**Interfaces:**
- Consumes: the I3 GREEN workspace (sim_runner with harness-mode ingest, brief, config), MCP tools from `mcp-tools.md`.
- Produces: one branch per campaign; one batch per iteration with `version` and a one-line name.

- [ ] **Step 1: Write `$SKT/iterate/scenarios.md`**

```markdown
# signalflag-iterate scenarios

## T1 — tune the gain (the I3 GREEN workspace)
Prompt: "Tune the controller gain in run_suite.py to minimize final error across scenarios. Try at least three values."

Pass:
- One campaign branch for all iterations; a dashboard (or batch-level metric) on it shows the progression.
- Each iteration: code change → suite run → low-res ingest → MCP read-back → comparison with the previous → next decision stated.
- `version` differs per iteration (commit SHA or label); batch name says what changed in one line.
- Low-res for iterations; a high-res push only for the kept candidate.
- Final answer cites the SignalFlag numbers it read back, with the dashboard/batch link.
```

- [ ] **Step 2: RED**, **Step 3: GREEN** (required content: when it applies — a brief exists for the test type; the loop; one branch per campaign; version and batch naming; low-res default; MCP read-back by the real tool names), **Step 4: REFACTOR and finish** — per protocol. Commit: `git commit -m "signalflag-iterate: skill, proven against baseline"`.

---

### Task 9: End-to-end routing, retire /resim-run, session summary

**Files:**
- Delete (local, gitignored): `.claude/skills/resim-run/`
- Create: `$SKT/e2e/scenarios.md`, `$SKT/e2e/green.md`, `session_summaries/<date>-signalflag-skills.md`

- [ ] **Step 1: Retire `/resim-run` here** — confirm with the human partner, then `rm -rf .claude/skills/resim-run` (untracked; `.claude/` is gitignored, so this is not recoverable from git — confirm first). Copies in other local repos are untouched.

- [ ] **Step 2: E2E scenario** — all nine (or eight) skills installed. Fresh subagent, workspace `rl_project`, persona from O2, prompt: "I want my RL evals in SignalFlag, end to end." Pass: onboard runs first; skills load in brief order; structure-runs runs (needed here); a real low-res then high-res push; a dashboard link at the end; no `/resim-run`, CLI, Docker or credential files anywhere. 2 reps. Record in `$SKT/e2e/green.md`. Failures go back to the owning skill's REFACTOR.

- [ ] **Step 3: Session summary** — `session_summaries/<date>-signalflag-skills.md`, lean, for a fresh agent: what exists in `superflowers/`, how to install (symlink line), how to run the skill tests (`$SKT` layout, protocol), the signalflag-model decision and its counts, MCP tools found, traps found during testing, what's open.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/skill-tests/signalflag/e2e session_summaries/
git commit -m "SignalFlag skills: end-to-end routing verified; session summary"
```

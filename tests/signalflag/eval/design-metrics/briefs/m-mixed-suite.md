# Sim integration tests — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: pytest suite (`pytest` from repo root) against `minisim`, a 2D diff-drive sim with an in-process topic bus (`minisim/bus.py`). The `bus` fixture (`tests/conftest.py`) keeps every message as `bus.messages[topic] -> [(stamp_ns, msg)]`.
- Tests (8 items per run):
  - `tests/test_timing.py::test_timing_consistency` — 10 s sim, no obstacles, no wall control.
  - `tests/test_wall_follow.py::test_wall_follow[offset=0.3|0.5|0.8|1.2]` — 20 s each.
  - `tests/test_obstacle_stop.py::test_obstacle_stop[box_2m|box_4m|pallet_6m]` — 15 s each.
- Topics, at 50 Hz (DT = 0.02 s):
  - `clock` {sim_time_s, wall_time_s, rtf} — every test.
  - `odometry` {x, y, yaw, vx, wz} — every test.
  - `obstacle_state` {obstacle_id, distance_m, relative_speed_mps, in_path} at 10 Hz per obstacle — **only obstacle_stop tests**.
- Artifacts: none on disk. Everything lives in memory on the bus and is gone when the test ends. Nothing records the git commit, a dirty tree, or the sim parameters (speed, seed, offset/obstacle case are only in test code / param ids).
- Size: about 500–1000 msgs/topic/test; the whole suite runs in seconds.
- Frequency: runs locally on demand. No CI config in the repo.

## Intent
- Question: "Did this change to the sim or controller regress any of the integration tests, and by how much?" Today the suite only reports pass/fail. SignalFlag should show the margins (tracking error vs. 0.05 m, stop distance vs. 0.3 m, final speed, RTF, clock step) trend across runs.
- Who: the sim/controller developers (Karthik).
- Gate or exploration: regression gate. The existing asserts become status checks, and the trends are there to explore.
- Metrics-first. Each assertion already names a value and a threshold. The raw topics are uploaded as well so new SQL metrics can be added later.
- User requirement: **one dashboard layout shared by all tests.** Every test name gets the same charts. Charts that depend on `obstacle_state` must still render (or show a clear "n/a") for tests that lack that topic.

## Control
- Mode: A (agent decides; one stop at the metrics plan, before anything reaches SignalFlag).
- Metrics and events: agent-led.

## Mapping
In the user's words: each `pytest` run of the suite → one upload; each pytest item (file + parametrize id) → one row that compares against the same item in earlier runs.
- Project: `acme-robotics` (exists — confirmed by user: yes)
- Branch: `sim-int` (confirmed by user: yes)
- Batch is: one pytest session (all collected items in that run).
- Test is: the pytest node id minus the `tests/` prefix, e.g. `test_wall_follow.py::test_wall_follow[offset=0.3]`, `test_obstacle_stop.py::test_obstacle_stop[box_2m]`, `test_timing.py::test_timing_consistency` (chosen by agent — node ids are already stable and unique, and parametrize ids carry the case, so batches compare like-for-like. Renaming a test or param id starts a new series).
- Version is: `git rev-parse --short HEAD`, plus a `-dirty` suffix when the working tree has uncommitted changes (chosen by agent — there's no CI or build number, and the commit is what separates one run from the next. The dirty flag stops local edits from passing as the committed code).

## Integration
- Form: hook. A pytest plugin in the root `conftest.py` (currently empty) subscribes to the `bus` fixture's messages per test and emits them plus the computed metrics at teardown, then submits the batch at session end. Test files stay unchanged.
- Upload is opt-in (e.g. `--signalflag` flag or `SIGNALFLAG=1`), so plain `pytest` keeps working offline.
- structure-runs needed: no. The bus keeps every message per test, the node id gives the test name, and the hook can read the commit/dirty state from git at session start.
- Environment: the repo's pyproject. Add the SignalFlag SDK as an optional extra (`[project.optional-dependencies] signalflag = [...]`). No separate venv.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

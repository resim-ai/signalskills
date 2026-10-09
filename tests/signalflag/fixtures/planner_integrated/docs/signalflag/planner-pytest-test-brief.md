# Planner pytest — SignalFlag test brief

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: pytest. `tests/test_planner.py::test_plan` is parametrized over 4 scenarios: `open`, `one_box`, `corridor`, `clutter` (defined in `planner/plan.py:SCENARIOS`).
- Each case calls `plan(scenario)`, which returns a `Result` with `path_length_m`, `straight_m` and `min_clearance_m`, and asserts:
  - `path_length_m < 1.2 * straight_m` (detour ratio under 1.2)
  - `min_clearance_m > 0.25`
- Artifacts: none written to disk. The values exist only in memory during the test, and pytest records only pass/fail.
- Not recorded: git commit, dirty tree, `goal_x` (default 8.0), obstacle count per scenario.
- `conftest.py` exists but is empty. No CI config, no git remote. One commit on `master`.
- Size and frequency: 4 tests per run, each sub-second, run locally on demand.

## Intent
- Question: "Did this change to the planner make any scenario's path longer or its clearance tighter, and does every scenario still pass its thresholds?"
- Who: the planner developer, after each change. This works as a regression gate and a trend view over commits.
- Metrics-first: the asserted values are the metrics.

## Control
- Mode: A (agent decides). The user said "just do it… everything else is your call".
- Metrics and events: agent-led.

## Mapping
In the user's words: each `pytest` run is one upload. Each scenario case is one row. Each commit is one point on the trend.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `planner-pytest` (chosen by agent: one stable line per test type; the git branch `master` would be a bad name and could collide)
- Batch is: one `pytest` session
- Test is: the parametrize id, e.g. `test_plan[corridor]` (chosen by agent: this is pytest's own node id, so it stays stable across runs and batches compare scenario by scenario)
- Version is: the git commit short SHA, with `-dirty` appended when the tree has uncommitted changes (chosen by agent: each change is what you compare; the dirty flag stops edits that weren't committed from posing as the commit)

## Integration
- Form: hook, a pytest plugin in `conftest.py`. Results are captured per test, and the batch is uploaded at session end.
- structure-runs needed: no. The values are computed in the test, so the hook can emit them directly. No folder layout is involved.
- Environment: the project's `pyproject.toml`. Add the SignalFlag SDK to the `dev` extra. Uploading is opt-in through an env var, so a plain `pytest` run stays offline.

## Data profile
Source: called `planner.plan.plan()` directly for every scenario (2026-10-02, commit `66005c4`). Nothing exists on disk; these are the exact values the test asserts on. pytest isn't installed in the system Python, so this didn't go through pytest.

| Scenario | Obstacles | path_length_m | straight_m | Detour ratio (limit < 1.2) | Ratio margin | min_clearance_m (limit > 0.25) | Clearance margin |
|---|---|---|---|---|---|---|---|
| open | 0 | 8.000 | 8.0 | 1.000 | +0.200 | 5.00 (default, no obstacles) | +4.75 |
| one_box | 1 | 9.200 | 8.0 | 1.150 | +0.050 | 0.50 | +0.25 |
| corridor | 2 | 9.067 | 8.0 | 1.133 | +0.067 | 1.00 | +0.75 |
| clutter | 3 | 17.600 | 8.0 | 2.200 | **-1.000** | 0.20 | **-0.05** |

- Cadence: one scalar per field per test. There are no time series, states or modes.
- `straight_m` is constant (`goal_x` = 8.0). `min_clearance_m` saturates at 5.0 when there are no obstacles, so `open` is always far from the limit.
- The planner returns no path, only scalars. Obstacle `(x, y)` positions are known from `SCENARIOS`.

Failure-mode detectors, run on this data:
| Failure mode | Detector | Tests flagged |
|---|---|---|
| Detour too long | ratio >= 1.2 | 1 (clutter) |
| Clearance too tight | min_clearance_m <= 0.25 | 1 (clutter) |
| Harness failure (exception, unknown scenario, no Result) | missing result / pytest error outcome | 0 |
| Near-miss (pass, margin < 10% of limit) | ratio margin < 0.12 or clearance margin < 0.025 | 2 on ratio (one_box, corridor) |

`clutter` fails both assertions on the current commit, so today's `pytest` run is red. That's real, and it will be uploaded as a failure.

## Metrics plan
Control: agent-led. Approved by user: 2026-10-02.

| # | Question (from the brief) | Metric | Level | Template | Required? | Status check | Units | Threshold source | Description (one line) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | What actually ran? | scenario map | test | custom (Plotly XY) | required | — | m | — | Obstacles, start (0,0) to goal (8,0), the straight line, and the closest obstacle with its clearance marked. |
| 2 | Does this scenario pass, and by how much? | gate table: detour ratio and min clearance (value · threshold · margin · status) | test | table | required | block: ratio >= 1.2; block: clearance <= 0.25; block: result missing | ratio, m | spec: assertions in `tests/test_planner.py` | The test's two assertions, with distance to each limit. |
| 3 | Which scenario has the longest detour? | detour ratio by scenario, limit line at 1.2 | batch | bar | required | — | ratio | spec | Detour ratio per scenario against the limit. |
| 4 | Which scenario gets closest to obstacles? | min clearance by scenario, limit line at 0.25 | batch | bar | required | — | m | spec | Closest approach per scenario against the limit. |
| 5 | Did the run pass overall? | scenarios passing / total | batch | scalar | required | — | count | derived: row 2 | e.g. "3 / 4 passed". |
| 6 | Did this commit make a scenario worse? | detour ratio per scenario over commits | dashboard | line | required | — | ratio | spec | One line per scenario, with the 1.2 limit. |
| 7 | Did this commit tighten clearance? | min clearance per scenario over commits | dashboard | line | required | — | m | spec | One line per scenario, with the 0.25 limit. |

Templates: custom, table, bar, scalar, line. The test page has 2 rows, under the budget, on purpose. Each test only has two numbers, and the gate table plus the map cover them.

### Emitted, not charted
`path_length_m`, `straight_m`, `goal_x`, obstacle count, obstacle list `(x, y)`, pytest outcome (passed/failed/error), test duration, assertion message, git commit, dirty flag.

### Events
| Event | Trigger | Backing metric | Auto / User |
|---|---|---|---|
| Detour limit crossed | ratio >= 1.2 | row 2, row 3 | Auto |
| Clearance limit crossed | min_clearance_m <= 0.25 | row 2, row 1 | Auto |
| Near-miss | passes, but ratio margin < 0.12 or clearance margin < 0.025 (provisional: 10% of the limit) | row 2 | Auto |
| Harness failure | exception or error outcome, no Result; attaches a traceback excerpt | row 2 (result missing) | Auto |

No state-change events: the planner has no modes.

Open items (defaults):
- To capture `Result`, the test needs one small change: it passes `r` to a conftest fixture (`signalflag_record(r)`). The asserts stay unchanged.
- Upload is opt-in with `SIGNALFLAG_UPLOAD=1`. A plain `pytest` run stays offline.

## Config
- Path: `.resim/metrics/config.resim.yml`, plus the custom template `.resim/metrics/templates/raw.liquid` (`{{ raw_metric[0] }}`).
- Topics:
  - `planner_result`: scenario, path_length_m, straight_m, detour_ratio, ratio_limit, ratio_margin, min_clearance_m, clearance_limit, clearance_margin, goal_x, obstacle_count, passed. One row per test that produced a Result.
  - `test_outcome`: outcome, duration_s, message, git_commit, git_dirty. One row per test, always.
  - `scenario_map_fig`: raw_metric, the Plotly JSON built in `sf_pytest/figures.py`.
  - `planner_event`: an event topic.
- Metrics:
  - Test: Scenario Map (custom), Gate Table (table; blocks if either limit is crossed), Planner Result Present (scalar presence gate; blocks when the test produced no Result).
  - Batch: Detour Ratio by Scenario (bar), Min Clearance by Scenario (bar), Scenarios Passed (scalar).
  - Dashboard: Detour Ratio Over Commits (line), Min Clearance Over Commits (line).
- Sets: `Planner Pytest` (test and batch), `Planner Pytest Trends` (dashboard). Dashboard: `Planner Pytest Trends`.
- Every metric is required (`skip_if_no_data: false`).
- Checked so far: the YAML parses, and an offline dry run through the SDK Emitter (with validation on) accepted every row from all 4 tests plus a fake errored test.
- Not yet checked: scratch sync, previews, rendering. These wait on login.

## Ingest
- Code: `sf_pytest/` contains `records.py` (rows), `events.py` (pure detectors), `figures.py` (scenario map), `upload.py` (emits) and `plugin.py` (pytest hooks, Batch/Test). `conftest.py` loads it with `pytest_plugins = ["sf_pytest.plugin"]`.
- Test change: `tests/test_planner.py` names its limits (`MAX_DETOUR`, `MIN_CLEARANCE`) and calls `signalflag_record(...)` before asserting. The assertions are the same.
- Run: `SIGNALFLAG_UPLOAD=1 pytest [--sf-branch B] [--sf-version V] [--sf-max-tests N]`. `--sf-stride` and `--sf-no-media` are accepted but do nothing, since this suite has no series or media.
- The hook never starts a login. With no valid token it prints a message and skips the upload.

## Verification
_pending: signalflag-verify_

Next skills: signalflag-design-metrics → signalflag-auth → signalflag-compose-metrics → signalflag-ingest → signalflag-verify

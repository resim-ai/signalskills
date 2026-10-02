# Planner — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: pytest. `tests/test_planner.py::test_plan` is parametrized over 4 scenarios: `open`, `one_box`, `corridor`, `clutter` (defined in `planner/plan.py::SCENARIOS`).
- Each case calls `plan(scenario)` → `Result(path_length_m, straight_m, min_clearance_m)` and asserts:
  - `path_length_m < 1.2 * straight_m`
  - `min_clearance_m > 0.25`
- Artifacts: none. Nothing is written to disk; the computed values exist only in-process during the test. Only pass/fail survives a run.
- Not recorded: git commit, dirty-tree state, `goal_x` (default 8.0 used everywhere).
- `conftest.py` exists at repo root, empty. No CI config in the repo yet (branch name `planner-ci` implies it runs, or will run, in CI).
- Size/frequency: 4 tests, milliseconds per run; run per change / per CI build.

## Intent
- Question: "Did this change make the planner worse in any scenario — longer detours or tighter clearance — and how close is each scenario to its threshold?" Trend per scenario across builds.
- Who: planner developers, on each CI build.
- Gate (regression CI), metrics-first: the metrics are the values already asserted on.

## Control
- Mode: A (agent decides).
- Metrics and events: agent-led.

## Mapping
In their words: each run of the planner test suite checks four scenarios; each scenario yields a path length, straight-line distance and minimum clearance.
- Project: acme-robotics (confirmed by user: yes)
- Branch: planner-ci (confirmed by user: yes)
- Batch is: one pytest session (one suite run / one CI build).
- Test is: the scenario name — `open`, `one_box`, `corridor`, `clutter` (chosen by agent — the parametrize id is the stable identity across builds; using the bare scenario rather than `test_plan[open]` keeps names stable if the test function is renamed).
- Version is: the git commit SHA (short), suffixed `-dirty` when the working tree has uncommitted changes (chosen by agent — CI regression shape; a build is identified by its commit, and the suffix stops a local edited run masquerading as the committed code).

## Integration
- Form: hook — a pytest plugin in the existing root `conftest.py` that collects each scenario's `Result` and pushes one batch at session end.
- structure-runs needed: no — the values are available in-process at test time; the hook captures them directly.
- Environment: the project's `pyproject.toml` — add the SignalFlag SDK to an optional extra (e.g. `signalflag`), installed alongside `dev`.
- Open items:
  - Upload should be opt-in (env var / CI-only) so local `pytest` runs don't push without intent; and a missing token must not fail the test suite.
  - CI has no browser for device-code login — needs a non-interactive credential (resolved at signalflag-auth).

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

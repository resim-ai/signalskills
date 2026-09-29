# Planner tests — SignalFlag brief

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: pytest. `tests/test_planner.py::test_plan` parametrized over `open`, `one_box`, `corridor`, `clutter` (from `planner/plan.py` `SCENARIOS`).
- Each test calls `plan(scenario)` → `Result(path_length_m, straight_m, min_clearance_m)` and asserts `path_length_m < 1.2 * straight_m` and `min_clearance_m > 0.25`.
- `conftest.py` empty. Nothing written to disk; pass/fail on stdout is the only record. Values are lost after the run.
- Runs locally and in CI on every PR (per user). No CI config in this repo — open item.
- Size: 4 tests, 3 floats each, per run.
- From reading the code (not run — no python on this machine): `clutter` fails both checks (path 17.6 vs 9.6 limit; clearance 0.2 vs 0.25).

## Intent
- Question: how close each scenario is to its limits, and when one fails, how badly. Trended PR over PR.
- Asked by: planner developers on each PR; CI gate plus local checks.
- Metrics-first.

## Control
- Metrics and status checks: partial — agent proposes options, user picks thresholds/levels.
- Events: none beyond pass/fail; agent proposes if any emerge.

## Mapping
In the user's words: every pytest run (a PR's CI run or a local run opted in) is one upload; each scenario is one item compared run over run by name.
- Project: `skilltest-project` (confirmed by user: yes; exists, not to be created)
- Branch: `planner-ci`, CI and local runs both (confirmed by user: yes)
- Batch is: one pytest session with `--signalflag`
- Test is: bare scenario name — `open`, `one_box`, `corridor`, `clutter` (confirmed by user: yes)
- Version is: short git SHA in CI; `<short-sha>-dirty-<user>` for local runs with uncommitted changes (confirmed by user: yes)

## Integration
- Form: hook — `conftest.py` plugin collects `Result` per scenario, uploads one batch at session end.
- Opt-in: only with `pytest --signalflag` (or env var in CI); plain runs upload nothing (confirmed by user: yes).
- structure-runs needed: no — scenario name, all values and the commit are available in-process.
- Environment: codebase's own `pyproject.toml`, new optional extra `signalflag`; `pip install .` unchanged.
- Open items: no CI config in repo — where does CI live and how does it get credentials (no browser for device login)?

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

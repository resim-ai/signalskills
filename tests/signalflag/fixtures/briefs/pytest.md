# Planner tests — SignalFlag brief

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- `tests/test_planner.py::test_plan`, parametrized over `open`, `one_box`, `corridor`, `clutter` (from `planner.plan.SCENARIOS`).
- Each case calls `plan(scenario)` → `Result(path_length_m, straight_m, min_clearance_m)`.
- Asserts: `path_length_m < 1.2 * straight_m`; `min_clearance_m > 0.25`.
- Runner: plain `pytest`, locally and in CI on every PR. `conftest.py` empty; no CI config in repo.
- Writes nothing to disk — numbers exist only inside the assertions. No record of commit or dirty tree.
- Scenarios get added now and then.

## Intent
- Question: when a scenario fails, how badly, and what numbers are behind it; plus trend of those numbers build over build.
- Who: the user (planner dev), on PRs and locally.
- Gate + regression tracking. Metrics-first.

## Control
- Metrics and checks: partial — agent proposes, user picks.
- Events: none planned; agent proposes if useful, user picks.

## Mapping
In the user's words: every pytest run of the planner suite is one upload; every scenario is one entry, keeping its name.
- Project: `skilltest-project` (existing; do not create)
- Branch: `planner-ci` — single branch for PRs, main, and local runs (confirmed by user: yes)
- Batch is: one `pytest` session of `tests/test_planner.py`
- Test is: one parametrize id — `open`, `one_box`, `corridor`, `clutter`; new scenarios become new tests; names never renamed (confirmed by user: yes)
- Version is: git commit SHA, suffixed `-dirty` when the tree has uncommitted changes (confirmed by user: yes)

## Integration
- Form: hook — pytest plugin in `conftest.py`, collects each `Result`, uploads one batch at session end. Opt-in: upload only when `SIGNALFLAG_UPLOAD=1`.
- structure-runs needed: no — the test has every value in hand; version comes from git at session time.
- Environment: repo's `pyproject.toml`, new optional extra (e.g. `.[signalflag]`); core `dependencies` stays empty.
- Open items:
  - CI has no browser for device-code login — needs a non-interactive credential (signalflag-auth).
  - Capturing `Result` needs the test (or a fixture) to hand it to the plugin — design at ingest; no assertion changes.

## Data profile
- Per case: `path_length_m`, `straight_m` (8.0 always), `min_clearance_m`. Four cases; `clutter` fails both asserts (17.6 m vs 9.6 m limit; clearance 0.2 m). No time series, no media.

## Metrics plan
Control: partial (user picked).

| # | Question | Metric | Level | Template | Status check | Units | Threshold source | Description |
|---|---|---|---|---|---|---|---|---|
| 1 | What ran? | Result | test | table | — | m | — | The planner's numbers for this scenario. |
| 2 | How close to the path limit? | Path Ratio | test | scalar | block ≥ 1.2, warn ≥ 1.1 | ratio | block: the test's assert; warn: provisional | Path length over straight line. |
| 3 | How close to the clearance limit? | Clearance Margin | test | scalar | block < 0, warn < 0.05 | m | block: the test's assert; warn: provisional | Clearance minus 0.25 m. |
| 4 | Path vs straight | Path vs Straight | test | bar | — | m | — | Planned length against the straight line. |
| 5 | Distance to each limit | Margins | test | table | — | — | — | Negative means failed. |
| 6 | Which scenarios are worst? | Path Ratio by Scenario | batch | bar | — | ratio | — | Per scenario, this run. |
| 7 | Which scenarios are worst? | Clearance Margin by Scenario | batch | bar | — | m | — | Per scenario, this run. |
| 8 | Getting worse over commits? | Path Ratio Trend | dashboard | line | — | ratio | — | Per scenario, by build time. |

### Emitted, not charted
`passed` per case.

### Events
| Event | Trigger | Backing metric | Auto / User |
|---|---|---|---|
| Assertion failed | a case's assert fails | Margins | Auto |

## Config
- Path: `.resim/metrics/config.resim.yml` (+ none custom).
- Topics ingest must emit: `plan_result` (scenario, path_length_m, straight_m, min_clearance_m, path_ratio, clearance_margin_m, passed) — one emit per case; `planner_event` (event) for failed assertions.
- Sets: `Planner Tests`; `Planner Trends` → dashboard `Planner Trends`.
- Scratch sync accepted 2026-09-28.

## Verification
_pending: signalflag-verify_

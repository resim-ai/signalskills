# Nav sim scenarios — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: `harness/run.py` (`python -m harness.run --scenarios harness/scenarios --out results`). It iterates every `harness/scenarios/*.yaml`, runs it, and writes `results/<scenario>/metrics.json` through `harness/metrics.py::write_metrics`.
- Scenarios (3): `empty_room`, `narrow_door`, `cluttered_aisle`. Each one sets a world, a start pose, a goal, `timeout_s: 60` and obstacles.
- Per-scenario artifact (planned): `ScenarioMetrics` with `scenario`, `reached_goal` (bool), `time_to_goal_s`, `min_obstacle_distance_m`, `path_length_m`, `collisions` (int). It's one small JSON per scenario. `metrics.py` notes that the fields may still change.
- **Nothing has run yet.** `run_scenario` raises `NotImplementedError` because Gazebo isn't wired up. The TODO plans to record `/odom` and `/scan`, but nothing persists those recordings yet. `results/` is gitignored and doesn't exist.
- Not recorded by the harness: git commit, dirty tree, sim/stack versions, scenario file hash, wall-clock or seed.
- Cadence (planned): every PR, from the `harness-dev` git branch.

## Intent
- Question: "Did this PR make the nav stack worse in any scenario?" This is a per-PR regression gate. Whoever reviews the PR checks whether each scenario still reaches the goal without collisions, and whether time, path length and clearance have drifted.
- Metrics-first. The fields are already defined and are what you'd assert on. Trajectory (`/odom`) and scan data could be added later as data-first topics once the harness saves them.

## Control
- Mode: A (agent decides). Chosen by the user.
- Metrics and events: agent-led. The one stop is after the metrics plan, before anything logs in, installs or uploads.

## Mapping
In the user's words: every PR run of the three scenarios is one report, and each scenario inside it is one line item.
- Project: `acme-robotics` (confirmed by user: yes; exists, not to be created)
- Branch: `harness-dev` (confirmed by user: yes. It overrides the agent's `nav-sim-regression`. Every PR batch goes to `harness-dev`, so dashboards and trends read that branch. If the work later moves to another git branch, keep reporting to `harness-dev` to preserve the history)
- Batch is: one full run of `harness.run` over all scenarios, i.e. one PR CI run
- Test is: the scenario `name` (`empty_room`, `narrow_door`, `cluttered_aisle`) (chosen by agent: it's already the stable key in the YAML and the results folder, so batches compare scenario to scenario)
- Version is: the git commit SHA under test (`GITHUB_SHA` or `git rev-parse HEAD`, with a `-dirty` suffix when the tree isn't clean) (chosen by agent: on per-PR CI, the commit is what makes one batch differ from the next. The harness doesn't record it today, so the runner has to capture it)

## Integration
- Form: harness. SignalFlag is wired into `harness/run.py`, emitting each scenario's `ScenarioMetrics` as it finishes, next to the existing `metrics.json` write, which is kept.
- structure-runs needed: no. The runner knows the scenario name and can read the commit at start-up. Nothing has to be reconstructed after the fact.
- Environment: the repo has no dependency manager yet (only `yaml` is imported). Add a `requirements.txt` (or `pyproject.toml` with a `signalflag` extra) listing `pyyaml` and the SignalFlag SDK, and have CI install it into a venv.
- Implemented: `python -m harness.run --signalflag [--branch harness-dev] [--version SHA] [--max-tests N]`. `harness/sf_rows.py` is pure rows and events; `harness/sf_report.py` does the Batch/Test emits. Without `--signalflag`, the runner behaves as before. With it, each scenario is one Test. A scenario that raises is marked ERROR with its stacktrace attached, the run continues to the next scenario, and the exit code is 1. `metrics.json` is still written. The runner refuses to run without a valid token rather than starting a login. Local dev env: `.venv-signalflag/`; CI: `pip install -r requirements.txt`.
- Open items:
  - The sim isn't wired, so there's no real run to profile. The metrics plan will be based on the `ScenarioMetrics` schema, and verification has to wait for the first real `results/`.
  - `ScenarioMetrics` fields may change. Additions are safe on a branch (schemas only grow), but renaming or removing fields isn't.
  - The CI (PR) environment needs non-interactive SignalFlag credentials. This gets settled at `signalflag-auth`.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

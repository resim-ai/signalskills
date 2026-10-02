# Point-robot suite — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Runner: `run_suite.py` (`python run_suite.py --gain G --kd K`). One invocation runs all three scenarios: `straight`, `corner` and `slalom`. Each scenario is 150 steps at DT=0.1, so 15 s of sim time.
- Artifacts: `runs/<YYYYmmdd-HHMMSS>/<scenario>/`
  - `telemetry.csv`: 150 rows, `t_ns,x,y,err_m`
  - `results.json`: `scenario, gain, kd, final_error_m, sim_duration_s`
  - `frames/NNNN.png`: 120×120 px, one every 5 steps (30 per scenario)
- Existing runs: 5 invocations, 2026-09-28 to 2026-09-30, about 2.2 MB in total. The runs are a manual gain/kd tuning sweep: (0.5, –), (0.8, –), (0.8, 0.1), (1.0, 0.2), (1.0, 0.3).
- **What the runs don't record:**
  - **The code that produced them.** `run_suite.py` has uncommitted changes (kd term, FRAME_EVERY, timestamped folders) and `runs/` is untracked, so no run can be traced to a commit.
  - **Which code version.** `20260928-101512` and `20260928-154003` have no `kd` key, so an earlier version of the script produced them. Their frames still use the current 5-step stride.
  - **Any note or description of the run.**

## Intent
The user (Karthik) is tuning the controller by hand: try a gain and kd, run the suite, check whether final error and tracking got better. The question SignalFlag should answer is which gain/kd setting tracks best on each scenario and how the settings compare over time. This is exploration, not a CI gate. **Metrics-first:** final error and the error-over-time trace are already the things the user looks at.

## Control
- Mode: A (agent decides). Exceptions: the user chose the project, the branch and the version format.
- Metrics and events: agent-led.

## Mapping
In the user's words: each `run_suite.py` invocation is one tuning attempt, and each scenario inside it is one thing being checked.
- Project: `acme-robotics` (already exists, confirmed by user).
- Branch: `tuning` (confirmed by user: yes).
- Batch is: one `run_suite.py` invocation, i.e. one `runs/<stamp>/` folder.
- Test is: the scenario name (`straight`, `corner`, `slalom`). Chosen by agent: names are stable across runs, so batches compare scenario to scenario.
- Version is: `<YYYY-MM-DD> <note>`. The date comes from the run's folder stamp and the note is a short text the user types (confirmed by user: yes).
  - New runs: the note is given at run time and saved with the run (see Integration).
  - The 5 existing runs have no note. Proposed backfill note: the params, e.g. `2026-09-29 gain=0.8 kd=0.1`. For the two runs that predate kd: `2026-09-28 gain=0.5 (pre-kd code)` and `2026-09-28 gain=0.8 (pre-kd code)`. Confirmed by user: params as the note.
  - The version string doesn't capture the code, so the git commit and a dirty-tree flag are attached as batch metadata.
  - `gain` and `kd` are also recorded as batch-level parameters, so the dashboard can group by them whatever the note says.

## Integration
- Form: **script**. A separate `signalflag_ingest.py` reads `runs/<stamp>/` folders and pushes one batch per folder, skipping folders already pushed. It backfills the existing 5 runs and is re-run after each new invocation.
- structure-runs needed: **yes**. The version note and the code state can't be recovered from the artifacts. Small change to `run_suite.py`: add a `--note` arg and write `runs/<stamp>/run.json` containing `{note, gain, kd, git_commit, git_dirty, started_at}`. The ingest script reads it if present and falls back to the backfill rule above if not. The rest of the existing uncommitted `run_suite.py` changes stay untouched.
- Environment: separate venv at `.venv-signalflag/` in the repo. The repo has no dependency manager, and the runner itself needs no SignalFlag dependency.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

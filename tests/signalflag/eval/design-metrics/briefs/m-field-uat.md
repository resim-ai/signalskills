# Field UAT — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Manual acceptance testing on real rovers before each release, from written cases in `uat/cases/`:
  UAT-003 e-stop, UAT-006 autonomous docking, UAT-012 obstacle stop, UAT-018 path retrace.
- No harness. A field tech runs each case and records a bag with `scripts/record_case.sh <release> <case> <robot> <n>`
  → `field/<release>/<case>_<robot>_<n>.mcap` (~50–180 KB each). Topics: `/odom`, `/localization/pose`, `/diagnostics`,
  `/estop/state`, `/docking/state`, `/route/status`, `/perception/nearest_obstacle`.
- The tech fills in `field/<release>/results.csv` by hand: `case,robot,run,result(PASS|FAIL),notes`.
  **The verdict is a human judgement.** Some pass criteria can't be measured from the bag at all
  (UAT-006 dock-plate alignment marks; UAT-018 deviation "judged by eye against the chalk line").
- Three releases so far: `4.11.0-rc3` (5 runs), `4.12.0-rc1` (5 rows, 4 bags), `4.12.0-rc2` (6 runs). Robots: rover-07, rover-11.
  Which robot and how many runs per case changes from release to release; repeat runs (`_2`) happen after a failure or just as a re-check.
- What isn't recorded: build/commit on the robot beyond the release tag, date, tech, site conditions (only sometimes in notes, e.g. "wet grass").
- Known gap: `4.12.0-rc1` UAT-012 rover-11 run 1 is PASS in the CSV but has no bag ("recording not started, forgot").

## Intent
- Question: "Is this release candidate as good as the last one in the field? Which UAT cases got better or worse, and on which robot?"
  Asked by the release owner / field team before each release; used as a release gate, with trends across releases.
- Metrics-first. The tech's PASS/FAIL is the gating verdict; measured values from the bags (stop distance, dock time, retries,
  obstacle clearance, resume time, path tracking) sit next to it to show *how close* each run was and to catch drift a PASS hides.
- Measured checks never override the human verdict; when they disagree, that is surfaced as a finding, not silently resolved.

## Control
- Mode: A (agent decides). One stop: after the Metrics plan, before anything reaches SignalFlag.
- Metrics and events: agent-led.

## Mapping
In their words: each release's field session (one `field/<release>/` folder) is one upload; each recorded case run is one item in it.
- Project: acme-robotics (confirmed by user: yes; exists, don't create)
- Branch: `uat` (confirmed by user: yes — changed from agent's `field-uat` at the go; one line of field-acceptance batches across all releases, kept separate from any sim/CI branches)
- Batch is: one release folder `field/<release>/` — all UAT runs done for that release candidate.
- Test is: `<case>_<robot>_<n>`, the bag file stem, e.g. `UAT-006_rover-11_2` (chosen by agent — it's the unit the tech records and judges; same robot+case+run compares directly across releases; per-case pass rates across robots/runs come from dashboard aggregation by case)
- Version is: the release tag, e.g. `4.12.0-rc2` (chosen by agent — it's the folder name and the thing being accepted). Batches are pushed in release order.

## Integration
- Form: script — an ingest script over `field/<release>/` (results.csv + bags), re-run once per release after the tech fills in the CSV. Lives in `signalflag/`, separate from the recording workflow.
- structure-runs needed: no — release comes from the folder, case/robot/run from the file name, verdict and notes from results.csv.
- Environment: own venv at `signalflag/.venv` (gitignored).
- Open items:
  - CSV rows without a bag (rc1 UAT-012 rover-11 run 1): upload as a test with the verdict and notes only, flagged "no recording"; no measured metrics.
  - Bags without a CSV row (none today): upload measured data, verdict "not recorded", flagged.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

# Fleet shift logs — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- No test harness or sim. Real shift recordings from the warehouse AMRs at site `warehouse-a` (`fleet.yaml`).
- `scripts/record_shift.sh` (systemd, on each robot) records one mcap per shift: `/data/logs/<robot>/<UTC date>`. The nightly sync copies it to `logs/<robot>/<YYYY-MM-DD>.mcap` in this repo.
- Topics: `/odom` and `/localization/pose` (throttled to 1 Hz), `/gps/fix` (amr-03 yard only), `/diagnostics` at 0.2 Hz (localization, autonomy mode, battery), `/teleop/takeover` (event: operator e-stop / takeover).
- At present: 7 shifts, 21–24 Sept 2026, about 270–320 KB each. amr-01 ×3, amr-02 ×2, amr-03 ×2. That is one ISO week (2026-W39). A robot doesn't record every day.
- Not recorded: ground truth, software or build version on the robot, shift or operator ID. The date is the UTC date at shift start.

## Intent
- The question: **how many interventions per hour of autonomy, by robot and by week?** It's asked by the fleet team lead for a Monday review.
- Exploration and trend, not a gate. A threshold should flag a bad robot-week, not block anything.
- Metrics-first: the headline is interventions per autonomy-hour. Supporting numbers are raw intervention count and autonomy hours.

## Control
- Mode: A (agent decides). The user gave the project and the headline metric.
- Metrics and events: agent-led, except the headline metric (interventions per autonomy-hour), which the user chose.

## Mapping
In the user's words: each Monday review covers one week. Each robot is a row, and its shifts that week add up into that row.
- Project: `acme-fleet` (confirmed by user: yes)
- Branch: `warehouse-a-weekly` (chosen by agent: one branch per site, so the dashboard trends every week together. A second site would get its own branch.)
- Batch is: one ISO week of shifts, e.g. all logs dated 2026-09-21 … 2026-09-27.
- Test is: one robot, `amr-01`, `amr-02`, `amr-03` (chosen by agent: robot names stay the same week to week, so tests line up across batches and the dashboard can trend each robot. Each shift is detail inside that robot's test, not its own test, because a shift date never repeats.)
- Version is: the ISO week, `2026-W39` (chosen by agent: the robots record no build or software version, and what separates one batch from the next is the week.)

## Integration
- Form: **script**. A standalone ingest over `logs/<robot>/<date>.mcap`, run once a week before the Monday review (by hand or cron). It takes an `--week` argument (default: last complete ISO week).
- structure-runs needed: no. The path gives the robot and date, and the week comes from the date. Interventions come from `/teleop/takeover`, and autonomy time from the autonomy mode in `/diagnostics`.
- Environment: separate venv at `.venv-signalflag/` (the repo has no Python dependency manager).

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

# Field localization — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- No harness and no runner. `scripts/record_shift.sh` runs on each robot (via systemd, from shift start to shift end) and records one mcap per shift. The nightly sync then copies it to `logs/<robot>/<YYYY-MM-DD>.mcap`.
- Fleet (`fleet.yaml`): site `warehouse-a`. amr-01 works aisles-north, amr-02 aisles-south, amr-03 the yard (amr-03 is the only one with GNSS).
- What's on disk now: 7 shifts, about 265–320 KB each. amr-01: 09-21, 09-22, 09-24. amr-02: 09-21, 09-23. amr-03: 09-22, 09-24. Not every robot records every day.
- Topics. Messages are JSON-encoded in the mcap.
  - `/odom` (nav_msgs/Odometry, throttled to 1 Hz, `odom` frame)
  - `/localization/pose` (PoseWithCovarianceStamped plus an extra `match_score` field, 1 Hz, map frame)
  - `/gps/fix` (NavSatFix, 1 Hz, amr-03 only)
  - `/diagnostics` (0.2 Hz). It includes a `localization` status (level 0/1, e.g. "pose uncertainty high", with `particles` and `map` values), `autonomy` (AUTO/MANUAL plus `mission`), and `battery`.
  - `/teleop/takeover` (event, with `reason`, `source`, `operator_id`)
- What the logs don't record:
  - **No ground truth.** Drift can only be estimated from stand-ins: localizer vs odometry disagreement, covariance, `match_score`, diagnostics warnings, takeovers, and GNSS on amr-03.
  - No localizer build or commit, and no config beyond `particles` (800) and `map` (`warehouse-a_v14` in every current log).
  - The throttle to 1 Hz caps the time resolution.

## Intent
- The question: **Is localization drifting on any robot, where, and is it getting worse from shift to shift?** People open SignalFlag to watch it per robot over time and to find the shifts and stretches worth digging into.
- Who asks: the fleet/localization team.
- Exploration and monitoring, not a release gate. Status checks warn rather than block until the thresholds have been tuned on real data. The user explicitly asked for "reasonable" starting thresholds.
- Metrics-first: per-shift drift stand-ins, plus time series and events for the bad stretches.

## Control
- Mode: A (agent decides). The user supplied the project and the branch.
- Metrics and events: agent-led. The user asked for reasonable thresholds, so the agent chooses them in design-metrics and revisits them after the first real batches.

## Mapping
In the user's words: each night's sync brings in the shifts for that day, one per robot that ran. You want to see each robot's localization over time.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `fleet-loc` (confirmed by user: yes)
- Batch is: one shift date across the fleet, i.e. one nightly sync (`logs/*/<date>.mcap`). The current data gives 4 batches (09-21, 09-22, 09-23, 09-24).
- Test is: the robot, named exactly `amr-01`, `amr-02`, `amr-03` (chosen by agent). This keeps names stable across batches, so the dashboard can trend each robot day over day. A robot with no shift that day is simply absent from that batch.
- Version is: the shift date, `YYYY-MM-DD` (chosen by agent). It's the only thing that differs between nightly syncs. The map version (`warehouse-a_v14`) and particle count go in as batch/test metadata so that a map change shows up when trends shift.

## Integration
- Form: **script**. It's an ingest over `logs/<robot>/<date>.mcap`, run once per new date (by hand, or after the nightly sync). It doesn't touch `record_shift.sh` or the robots.
- structure-runs needed: no. The path gives robot and date, and the diagnostics give map and particles. The missing localizer build is recorded as an open item, not a blocker.
- Environment: its own venv at `.venv-signalflag/` in this repo, gitignored. The repo has no Python dependency manager.
- Open items:
  - No localizer build/commit in the logs. If you want trends attributed to localizer releases, the recorder will need to log it later.
  - "Drift" is a stand-in metric, since there's no ground truth. The GNSS cross-check works for amr-03 only.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

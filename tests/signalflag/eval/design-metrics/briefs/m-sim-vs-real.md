# Perception replay, real and sim — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- `replay/run_replay.py` plays recorded front-camera drives (`scenarios/*.yaml`, 5 scenes) through the perception stack (`acme/perception`, tag in compose.yaml), writing `outputs/<scenario>/replay.mcap` (detections, tracks, latency, diagnostics), `camera.mp4`, `replay.gif`; labels in `labels/`.
- `--source sim` runs the same stack on drives rendered in the yard digital twin: `sim/outputs/<scenario>/`, 3 scenes, each mirroring a real one (`sim/scenarios/*.yaml: mirrors`); sim labels are exact.
- Latency budget 100 ms.

## Intent
Metrics-first. The perception engineer tracks each source and the sim-to-real gap for the same scene: where sim is optimistic or pessimistic, per class.

## Control
Mode: B (guided). Metrics and events: partial — agent proposes, user picks.

## Mapping
In the user's words: each replay of a stack build on real drives, and on sim drives, is one run each; same scenes are compared across the two.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `perception-replay` (confirmed by user: yes)
- Batch is: one replay invocation per source per stack build.
- Test is: the scenario name (`night_parking_lot`, `sim_lot_night`); each sim test carries `mirrors` (confirmed by user: yes)
- Version is: the image tag (confirmed by user: yes)
- System(s), test suite(s), metrics set(s): system `perception-stack`; suites `real-replay` and `sim-replay`; one shared metrics set (same data) (confirmed by user: yes)

## Integration
- Form: harness — a module `run_replay.py` calls after each scenario, for either source.
- structure-runs needed: no.
- Environment: `.venv-signalflag/`, git-ignored.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

# Perception replay — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- `replay/run_replay.py` plays each of 5 recorded front-camera drives (`scenarios/*.yaml`: day_parking_lot, night_parking_lot, rain_crosswalk, crowded_loading_dock, highway_merge_far) through the perception stack (`acme/perception` image, tag in `compose.yaml`) and writes `outputs/<scenario>/replay.mcap` (`/camera/front/image` annotated, `/perception/detections`, `/perception/tracks`, `/perception/latency`, `/diagnostics`), plus `camera.mp4` and `replay.gif`.
- Ground-truth labels per frame in `labels/<scenario>.jsonl`; `perception/eval_utils.py` has an IoU matcher. Scoring against labels isn't wired up yet (README TODO).
- Latency budget: 100 ms camera-to-tracks (README). 10 Hz, 8 s per drive. Replays run on every stack release candidate.
- The stack's commit isn't recorded per run; the image tag is.

## Intent
Metrics-first. The perception engineer opens SignalFlag after a release-candidate replay to find what got worse and why — per class, per range, per scenario, tracking and latency — and to look at the frames. Debugging depth; gates on the agreed limits only (latency budget).

## Control
Mode: B (guided). Metrics and events: partial — agent proposes, user picks.

## Mapping
In the user's words: each replay of all five drives against a stack build is one run to compare with the last build.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `perception-replay` (confirmed by user: yes)
- Batch is: one invocation of `run_replay.py` over all scenarios = one stack build.
- Test is: the scenario name, e.g. `night_parking_lot` (confirmed by user: yes)
- Version is: the image tag from `compose.yaml`, e.g. `2026.09.4` (confirmed by user: yes)

## Integration
- Form: harness — a module `run_replay.py` calls after each scenario.
- structure-runs needed: no — every output already names its scenario and the image tag is in compose.yaml.
- Environment: `.venv-signalflag/`, git-ignored.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

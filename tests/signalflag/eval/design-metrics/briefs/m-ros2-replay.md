# Perception replay — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: `docker compose --profile replay up` starts the perception stack
  (`registry.acme.dev/perception/stack:<tag>`, currently `2026.09.3`, pinned in `compose.yaml`) and the
  `replay` container (`ros2-replay:humble-1.4.0`), which runs `replay/run_replay.py`.
- Runner: for each `scenarios/<name>.mcap` (4 today: `urban_intersection_01`, `highway_cut_in_02`,
  `parking_lot_03`, `night_ped_crossing_04`; ~120 KB each) it plays the bag at 1.0x with sim clock and records
  `/perception/detections` and `/perception/tracks`.
- Artifacts per scenario: `outputs/<name>/output.mcap` (~90–125 KB) and `outputs/<name>/replay.log`
  (scenario, bag path, recorded topics, `ros2 bag play` exit code).
- Config: `config/perception.yaml` (detector model/score threshold/classes, tracker type/max_age/min_hits),
  mounted read-only into the stack.
- Not recorded: which stack image tag or config produced an output; git commit or dirty tree; wall-clock
  run time. `outputs/` is **overwritten on every run**, so history exists only once uploaded.
- No labels and no grading yet (README TODO).
- Frequency: manual; rerun when the stack tag is bumped or config is tuned.

## Intent
- Question: "Did this stack build / config change how perception behaves on our scenarios, and where?" —
  compare a new image tag or config against previous runs, scenario by scenario.
- Asked by: the perception team, when bumping the stack tag in `compose.yaml` or tuning `perception.yaml`.
- Exploration for now, not a gate: without labels there's no ground truth to block on. Status checks
  only on things that are clearly broken (replay failed, no detections, no tracks).
- Metrics-first on label-free signals (detection/track counts, class mix, scores, track lifetimes,
  publish rates/latency); raw detections and tracks also kept as topics, so accuracy metrics can be added
  as SQL once labels exist.

## Control
- Mode: A (agent decides), except project and branch, which the user gave.
- Metrics and events: agent-led; one stop for review after the metrics plan, before anything reaches SignalFlag.

## Mapping
In their words: "a replay" (one `compose up`) plays all scenarios against one stack build + config.
- Project: `acme-robotics` (confirmed by user: yes; exists, never created by us)
- Branch: `perception-replay` (confirmed by user: yes)
- Batch is: one replay run — all scenarios in `outputs/` after one `docker compose --profile replay up`.
- Test is: the scenario name, the bag stem (`urban_intersection_01`, …) (chosen by agent — stable across
  runs, so the same scenario lines up batch to batch; new bags become new tests automatically)
- Version is: the perception stack image tag, e.g. `2026.09.3`, plus `+cfg-<sha8>` of
  `config/perception.yaml` when it differs from the committed file (chosen by agent — the tag is what the
  README says you bump to test a build; the config suffix keeps config-tuning runs on the same tag apart).
  Git commit and the full config go in as batch metadata.

## Integration
- Form: script — `tools/signalflag/ingest_replay.py` (readers/replay_mcap.py → derive.py + events.py → upload),
  run on the host after `compose up` finishes, reads `outputs/*/` and pushes one batch. Flags: `--branch --version
  --max-tests --stride --no-media --dry-run --assume-stack-image`. The batch API has no metadata field, so git commit,
  dirty flag, stack image, config sha and provenance are columns of `run_summary`; `run.json` (incl. full config)
  is attached to every test. (Chosen over wiring into `run_replay.py`: that runs inside a pinned
  third-party ROS image with no SDK or credentials, and the host already has every artifact.)
- structure-runs needed: yes — outputs don't say which stack tag or config produced them, and compose.yaml
  can change between the run and the upload. Proposed change (made only after the go): `compose.yaml` passes
  `STACK_IMAGE` into the `replay` container; `run_replay.py` writes `outputs/run.json` (stack image, sha256 of
  the mounted config, start/end time, per-scenario exit code). The uploader refuses to push without it.
- Environment: separate venv at `tools/signalflag/.venv` (host Python, `mcap` + `mcap-ros2-support` + the
  SignalFlag SDK); nothing added to the containers.

### Open items
- Labels don't exist yet → no precision/recall; revisit once labels exist.
- Message schemas for `/perception/detections` / `/perception/tracks` to be confirmed from the mcaps
  (design-metrics).

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

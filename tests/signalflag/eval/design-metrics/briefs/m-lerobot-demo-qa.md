# Teleop demos — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- `data/` holds the teleop demo dataset: LeRobot v2.1 dataset `acme/so101_pick_cube`, robot `so101_follower`, 30 fps, one task ("Pick up the red cube and place it in the blue bin").
  18 episodes and 4208 frames, about 676 KB in total.
  - `data/data/chunk-000/episode_NNNNNN.parquet` has these columns per frame: `action` [6] and `observation.state` [6] (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper; all `.pos`), plus `timestamp`, `frame_index`, `episode_index`, `index` and `task_index`.
  - `data/videos/chunk-000/observation.images.top/episode_NNNNNN.mp4` is the 64×64 h264 top camera.
  - `data/meta/episodes.jsonl` holds per-episode length; `episodes_stats.jsonl` holds per-episode min/max/mean/std; `info.json` and `tasks.jsonl` hold the rest of the metadata.
- `collection_log.csv` maps each `episode_index` to its `operator` (op_a/op_b/op_c), `date` (2026-09-08 → 09-20) and `session` (s1–s3). It's filled by hand.
- Demos are recorded with `lerobot-record`. No script in the repo does the recording, and nothing records demo quality, success, or a reason for rejecting a demo. The dataset grows when someone records a new session.
- `scripts/train.sh` trains ACT on `data/`, and `scripts/eval_real.sh` does policy rollouts into `eval_data/` and `real_evals/*.csv`.
  Those rollouts are a **separate test type** (policy eval) and are out of scope for this brief.
- Already visible: episode 4 (op_b, s1) is 620 frames, while the others are 141–253.

## Intent
- Question: *are our teleop demos clean and consistent enough to train on? Which episodes are outliers, and is any operator or session systematically different?* The user asked about this ("look at the quality of our teleop demos"). The audience is whoever curates the dataset before training.
- This is exploration and curation, not a hard gate. Flags should be `warn` so they point at episodes to review or drop, not block anything.
- Metrics-first: per-episode quality metrics (duration, smoothness/jerk, idle time, action–state tracking error, gripper open/close events, joint-limit proximity, frame/timestamp gaps), plus per-frame timeseries so a flagged episode can be inspected.

## Control
- Mode: A (agent decides). The user supplied the project and the branch.
- Metrics and events: agent-led. The user gets one review stop after the metrics plan and before anything is installed, logged in or uploaded.

## Mapping
In the user's words: each episode is one demo, and we check the whole demo set every time it changes. In SignalFlag terms, each snapshot of the dataset is a *batch* and each episode is a *test* in it.
- Project: `acme-robotics` (given by user; not created, it is looked up at auth)
- Branch: `demo-qa` (confirmed by user: yes)
- Batch is: one quality pass over the whole `data/` dataset as it stands. It's re-run after each new recording session.
- Test is: one episode, named `episode_000004` etc. from `episode_index`, with operator, session and date attached from `collection_log.csv` (chosen by agent — LeRobot's own stable episode id; batches then compare the same episode across re-runs, and the operator/session tags allow grouping)
- Version is: the git short SHA of the commit containing `data/` plus the episode count, e.g. `eefe9a1-ep18` (chosen by agent — the dataset is versioned in git and has no version field of its own; the episode count makes it readable when sessions are added)

## Integration
- Form: script. A standalone ingest script runs over `data/` (parquet + meta) joined with `collection_log.csv`, and is re-run after each recording session. There is no harness to hook into, because recording is done by `lerobot-record` from the CLI.
- structure-runs needed: no. Every episode file carries `episode_index`, and operator/session join on it from `collection_log.csv`. The dataset is versioned by git.
  Open item: a dirty working tree (uncommitted new episodes) gives no meaningful SHA. The script should then append `-dirty` to the version.
- Environment: separate venv at `.signalflag-venv/` (git-ignored). The repo has no Python dependency manager, only shell scripts that call `lerobot-*`.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

# ACT real-arm checkpoint eval — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- **Training** (`scripts/train.sh`): `lerobot-train`, ACT on `acme/so101_pick_cube` (`data/`, 18 teleop episodes,
  3 operators, see `collection_log.csv`), 100k steps, `save_freq=20000`, seed 1000, wandb off. Checkpoints in
  `outputs/train/act_pick_cube/checkpoints/<step>/` (020000 … 100000). No training-loss log is kept.
- **Real-arm eval** (`scripts/eval_real.sh <step>`): `lerobot-record` on SO-101 `arm_a`, policy = that checkpoint,
  10 episodes × 20 s max, top camera, task "Pick up the red cube and place it in the blue bin". Episodes are
  **appended** (`--resume=true`) to the LeRobot v2.1 dataset `eval_data/` (`acme/eval_act_pick_cube`): per-frame
  `action`/`observation.state` (6 joints), mp4 video, per-episode stats.
- **Operator sheet**: `real_evals/<step>.csv` filled by hand — `trial, success (yes/no), time_s, notes`
  (free-text failure modes: "placed next to bin", "knocked cube off table", "re-grasped once", …).
- Today: 4 sessions (040000, 060000, 080000, 100000) = 40 eval episodes; 020000 never evaluated.
- **Not recorded anywhere**: which checkpoint produced which `eval_data` episode — only append order.
  Verified by hand: episode `i` ↔ checkpoint `[040000,060000,080000,100000][i//10]`, trial `i%10+1`
  (episode duration matches operator `time_s` within ~0.7 s for all 40). Also not recorded: git commit, robot/
  camera setup changes, cube start pose.

## Intent
"Which checkpoint is best on the real arm, and is training still helping?" — asked by whoever trains the policy
before picking a checkpoint to keep or deploy. Exploration / leaderboard, not a gate. Metrics-first (success rate,
time-to-complete, failure-mode counts), with per-trial trajectories and video available to drill into.

## Control
- Mode: A (agent decides).
- Metrics and events: agent-led.

## Mapping
In your words: each `eval_real.sh <step>` session is one checkpoint's report card; each of its 10 trials is one row
of the operator sheet plus one recorded episode.
- Project: `acme-robotics` (confirmed by user: yes — exists already)
- Branch: `act-pick-cube` (confirmed by user: yes)
- Batch is: one real-arm eval session of one checkpoint (10 trials). Re-evaluating a checkpoint = a new batch.
- Test is: `trial_01` … `trial_10` (chosen by agent — matches the operator sheet; each test carries that trial's
  success/time/notes plus its episode's joint trajectories and video. Batch-level metrics give the checkpoint score.)
- Version is: the checkpoint step, e.g. `040000` (chosen by agent — it's the only thing that changes between
  sessions; a dashboard on the branch then trends/ranks by step).

## Integration
- Form: **script** — `signalflag/ingest_real_evals.py <step>` (or all steps) reads `real_evals/<step>.csv` + the
  matching `eval_data` episodes and pushes one batch. Re-run after each eval session. `scripts/eval_real.sh` and
  `lerobot` stay untouched apart from the structure-runs change below.
- structure-runs needed: **yes** — the eval dataset doesn't record which checkpoint made each episode. Change:
  `eval_real.sh` writes `real_evals/<step>.episodes.json` (`{"step", "first_episode", "num_episodes", "date",
  "robot_id"}`) by reading `eval_data/meta/info.json` `total_episodes` before and after recording. Backfill the four
  existing sessions from the verified order mapping above. The ingest script refuses a step without this sidecar.
- Environment: own venv `.venv-signalflag/` in the repo (gitignored), `signalflag` SDK + `pandas`/`pyarrow`.

## Open items
- 020000 has no real-arm eval — dashboard starts at 040000 unless you run it.
- `time_s` (operator) vs episode duration (recorded) differ slightly; design-metrics picks one as authoritative.
- Training data / operator quality (`collection_log.csv`) is a separate, neighbouring brief if wanted.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

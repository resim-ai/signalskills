# Robomimic rollouts (diffusion policy) — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Policy: `diffusion_unet_lowdim` on robomimic `lift`, `can`, `square` (PH, low-dim); config `configs/dp_lowdim.yaml`.
- Training writes `ckpts/epoch_<n>.pt` every 100 epochs (500 total; `ckpts/` not in git).
- Runner: `python rollout.py --ckpt ckpts/epoch_<n>.pt` → `rollouts/epoch_<n>.hdf5`, one file per checkpoint.
- Each file: 50 rollouts per task (150 total), robomimic layout `data/demo_<i>/{obs/*,actions,rewards,dones}`;
  per-demo attrs `success`, `task`, `num_samples`, `seed`; file attrs `data.total`, `data.epoch`, `data.ckpt`.
- Rollout horizons: lift 30, can 45, square 60 steps at 10 Hz; seeds `100000 + r`.
- On disk now: `epoch_100`, `epoch_200`, `epoch_300` (~0.8–0.9 MB each).
- Not recorded in the h5: git commit, config contents (only the ckpt path and epoch).

## Intent
Metrics-first exploration (not a gate): "How does each task's success rate change across checkpoints, and which
epoch is best?" Asked by the user while training. Core view: success rate per task trended over epochs.

## Control
- Mode: B (guided).
- Metrics and events: partial — user fixed the core (per-task success rate over epochs); agent proposes additions,
  user accepts or rejects each.

## Mapping
In the user's words: each checkpoint's rollout file is one result; within it, lift, can and square are compared
across epochs.
- Project: `acme-robotics` (exists; confirmed by user)
- Branch: `dp-robomimic` — fixed name, not read from git (repo is on `master`) (confirmed by user: yes)
- Batch is: one checkpoint's rollout file, `rollouts/epoch_<n>.hdf5`
- Test is: one per task — `lift`, `can`, `square` (from demo attr `task`) (confirmed by user: yes)
- Version is: `epoch_<n>` from `data.attrs["epoch"]` (confirmed by user: yes)

## Integration
- Form: script — `signalflag/ingest.py rollouts/`, re-run after each new checkpoint; one batch per `epoch_<n>.hdf5`.
- structure-runs needed: no — each file records its epoch and ckpt, and each demo its task and success.
- Environment: separate venv at `signalflag/.venv` (keeps `rollout.py`'s torch/robomimic env untouched).

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

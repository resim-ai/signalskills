# PPO reach lr sweep — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: `sweep.sh` loops `train.py` (stable-baselines3 PPO on `ReachTarget-v1`, 8 envs, batch 256, gamma 0.99)
  over lr ∈ {1e-4, 3e-4, 1e-3, 3e-3} × seed ∈ {0, 1, 2}, 1M env steps each.
- Artifacts per run, in `sweep/lr_<lr>/seed_<s>/`:
  - `config.json` — algo, env, lr, seed, total_steps, n_envs, batch_size, gamma.
  - `progress.csv` — `step, mean_return, success_rate`, one row per eval every 10k steps (100 rows for a full run).
- Size: 12 runs, ~1.2k rows total. Sweep is finished; run once, not on a schedule.
- Not recorded: git commit / dirty tree, checkpoint path, wall-clock time, why a run stopped.
- **Incomplete run:** `lr_3e-3/seed_2` ends at step 610k (61 rows), no error recorded. The other 11 reach 1M.

## Intent
Which learning rate to use for PPO on reach. Asked by the user (Karthik), exploration, not a gate.
Metrics-first. Two views wanted:
1. Final mean return per lr, with the spread over the 3 seeds (ranked).
2. Learning curves (mean_return, success_rate vs step), seeds overlaid, per lr.

## Control
- Mode: B (guided).
- Metrics and events: agent-led, one stop before anything is uploaded to SignalFlag.

## Mapping
In the user's words: one upload per learning rate, each seed an entry in it.
- Project: `acme-robotics` (exists; confirmed by user: yes)
- Branch: `lr-sweep-sept` (confirmed by user: yes)
- Batch is: one learning rate — the 3 seed runs of `sweep/lr_<lr>/` (4 batches). `config.json` values attached to the batch.
- Test is: one seed run, named `seed_0`, `seed_1`, `seed_2` (confirmed by user: yes)
- Version is: the lr string as in the folder name — `1e-4`, `3e-4`, `1e-3`, `3e-3` (confirmed by user: yes)
- Cross-lr ranking and curve comparison live on a dashboard on `lr-sweep-sept`.

## Integration
- Form: script — standalone ingest over `sweep/lr_*/seed_*/`, re-run when new sweep results land. `train.py` and `sweep.sh` unchanged.
- structure-runs needed: no — folder names and `config.json` give lr and seed; `progress.csv` has the curves.
- Environment: own venv at `tools/signalflag/.venv`, separate from the training environment.

Brief approved by user (mode B), 2026-10-02.

## Open items
- `lr_3e-3/seed_2` is truncated at 610k; user doesn't know whether it crashed or was killed. User delegated the
  final-return treatment to the agent, on condition it is flagged as incomplete. Resolved in the Metrics plan.
- No commit recorded per run; provenance is limited to `config.json`.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

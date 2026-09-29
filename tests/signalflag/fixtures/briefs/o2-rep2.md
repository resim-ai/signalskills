# Checkpoint eval — SignalFlag brief

Status: approved by user 2026-09-28.

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Runner: `eval_checkpoint.py <ckpt>`, run by hand on each new checkpoint while training continues. 5 seeds per checkpoint.
- Writes `evals/<YYYYmmddTHHMMSS>/episodes.csv` (columns `seed, return, success, episode_len`; 5 rows) and `log.txt` (`loaded checkpoints/ckpt_<step>`).
- On disk: 4 runs. `20260901T000000` = ckpt_10000, `20260901T010000` = ckpt_20000, `20260901T030000` = ckpt_40000. `20260901T020000` has no `log.txt`, so its checkpoint is unknown.
- Not recorded: git commit, eval params, dirty tree.
- Tests: `tests/test_eval.py` only checks that there are 5 rows. No CI.

## Intent
Rank checkpoints by mean return and success rate, and see whether training is still improving. Exploration/leaderboard, not a gate. Metrics-first.

## Control
Metrics and charts: agent-led with user approval. The agent proposes and the user approves before anything is saved.

## Mapping
In the user's words: each checkpoint eval is one entry on the leaderboard; the seeds are its episodes.
- Project: `skilltest-project` (exists; confirmed by user: yes)
- Branch: `ppo-lr3e4`, named after the training run (confirmed by user: yes)
- Batch is: one `evals/<stamp>/` folder = one checkpoint eval
- Test is: one per seed, `seed_0` … `seed_4` (confirmed by user: yes)
- Version is: checkpoint step, parsed from `log.txt` (`ckpt_<step>` → `<step>`)

RL case: evaluated as a training run. One batch per eval cycle, one branch, and a dashboard ranks checkpoints and trends them against step.

## Integration
- Form: script. A separate sync script over `evals/*/` uploads folders not yet on SignalFlag. `eval_checkpoint.py` is untouched, so a failed upload cannot break an eval. Also backfills the 3 existing known runs.
- structure-runs needed: no. `log.txt` records the checkpoint for every run except `20260901T020000`, which is excluded.
- Environment: own venv for the sync script, outside the eval code's dependencies.

### Open items
- `evals/20260901T020000`: checkpoint unknown, excluded until the user confirms it.
- The sync script needs a rule for skipping folders that are already uploaded (e.g. match by version on the branch). Decide in ingest.
- A future eval run with a missing `log.txt` should be skipped and reported, not guessed.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

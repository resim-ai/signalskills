# Checkpoint eval — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Runner: `eval_checkpoint.py <ckpt>` evaluates one RL checkpoint (e.g. `checkpoints/ckpt_10000`) over 5 seeds (0–4). Run by hand, one checkpoint at a time; no CI.
- Artifacts per run: `evals/<YYYYmmddTHHMMSS>/episodes.csv` (columns `seed, return, success, episode_len`; 5 rows) and `log.txt` (`loaded <ckpt>`, the only record of which checkpoint was evaluated).
- Not recorded: git commit, dirty tree, eval params beyond seeds. The step is parsed from the checkpoint name (`ckpt_<step>`).
- Existing results: 4 runs from 2026-09-01, ~6 lines each:
  - `20260901T000000`: ckpt_10000
  - `20260901T010000`: ckpt_20000
  - `20260901T020000`: **no log.txt, checkpoint unknown** (open item)
  - `20260901T030000`: ckpt_40000
- `tests/test_eval.py`: a single pytest check that `evaluate()` returns 5 rows. It's a smoke test, not an eval, so it won't be uploaded.

## Intent
- Question: "Is the policy getting better as training goes on, and which checkpoint is best?" Return and success rate tracked against training step.
- Asked by: Karthik and their lead. This is for exploration and ranking, not a CI gate.
- Metrics-first: the CSV is small and fully structured.

## Control
- Mode: A (agent decides). The only user input was the project.
- Metrics and events: agent-led. The user approves once, at the go after the Metrics plan.

## Mapping
In your words: each time you run `eval_checkpoint.py` on a checkpoint, that run becomes one upload, and each of the 5 seeds in it is one row you can compare across checkpoints.

- Project: `acme-rl` (confirmed by user: yes)
- Branch: `checkpoint-eval` (chosen by agent: one branch so a single dashboard can trend and rank every checkpoint; named after the test type, not the git branch)
- Batch is: one eval run (one `evals/<stamp>/` folder = one checkpoint)
- Test is: one per seed, named `seed-<n>` (`seed-0` … `seed-4`) (chosen by agent: seeds are fixed (`range(5)`), so the names match across batches and the same seed can be compared checkpoint to checkpoint)
- Version is: the training step parsed from the checkpoint name, e.g. `10000` (chosen by agent: this is the "evaluated as training runs" RL case, and step is what the trend is plotted against. The checkpoint path is attached as batch metadata.)

## Integration
- Form: **hook**, an eval wrapper in this repo that uploads the new `evals/<stamp>/` after `main()` writes it. It comes with a backfill command that runs the same reader over existing `evals/*/` folders, used once for the 4 historical runs.
- structure-runs needed: no. New runs always write `log.txt` with the checkpoint. The one historical gap can't be fixed by changing the runner (see open items).
- Environment: the repo has no dependency manager (no pyproject/requirements, and numpy/pandas aren't installed in the system python). Plan: create `.venv/` in the repo and add a `requirements.txt` with `numpy`, `pandas` and the SignalFlag SDK. Created after the go.

### Open items
- ~~`evals/20260901T020000` has no `log.txt`.~~ **Resolved 2026-10-02:** re-running `evaluate()` for steps 0–100000 (every 1000) shows that only `ckpt_30000` reproduces its `return` and `episode_len` exactly. Ingest uses `checkpoints/ckpt_30000` for this folder and marks it in batch metadata as `checkpoint_source: inferred (re-evaluation match)`.
- No git commit is recorded per run, so batches won't be tied to code versions. That's acceptable for now.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

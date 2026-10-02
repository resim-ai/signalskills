# 3D detection checkpoint eval — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Model: `centerpoint_pillar` (`configs/centerpoint_v3.yaml`), 6 classes (car, truck, bus, pedestrian, bicycle, traffic_cone).
- Training (cluster) saves `runs/centerpoint_v3/ckpt_<epoch>.pth` every 5 epochs (30 epochs → ckpts 5, 10, 15, 20, 25, 30). `train.log` has per-epoch loss and lr.
- Runner: `python eval.py --ckpt runs/centerpoint_v3/ckpt_<N>.pth [--splits ...]`, run one checkpoint at a time.
- Artifacts: `eval/<epoch>/metrics_<split>.json`, one small JSON per val split (day 2410 samples, night 1180, rain 760). Each holds `split`, `epoch`, `checkpoint`, `mean_ap`, `nd_score`, `tp_errors` (trans/scale/orient/vel/attr), `label_aps` (class × dist threshold 0.5/1/2/4 m), `mean_dist_aps` (per class), `num_samples`.
- Present now: 6 epochs × 3 splits, except **epoch 20 rain is missing**. `eval/20/eval.log` shows a CUDA OOM on that split.
- Not recorded: the git commit, a config hash, or the training run id. Only the checkpoint path and epoch are written.

## Intent
- Question: "Which checkpoint should I ship, and is any split getting worse as training goes on?" Track mAP and NDS per split across epochs, and catch splits that diverge (night already falls after epoch 15 while day keeps rising).
- Who: the model owner (Karthik), when choosing a checkpoint after training.
- Use: exploration and ranking, with soft warn checks. Not a CI gate yet.
- Metrics-first: the metrics are already computed, so SignalFlag reports and charts them.

## Control
- Mode: A (agent decides). The user gave the project and branch.
- Metrics and events: agent-led.

## Mapping
In the user's words: each `eval.py` run on a checkpoint produces one result per val split, and you compare those across epochs.
- Project: acme-robotics (confirmed by user: yes)
- Branch: centerpoint-v3 (confirmed by user: yes)
- Batch is: one checkpoint's evaluation, i.e. one `eval/<epoch>/` folder.
- Test is: the val split: `day`, `night`, `rain` (chosen by agent: these names are stable across checkpoints, so every batch compares like with like, and the dashboard trends each split).
- Version is: `centerpoint_v3-ckpt_<epoch>`, e.g. `centerpoint_v3-ckpt_25` (chosen by agent: the epoch is the only thing that differs between batches and it is recorded in every JSON. The run name is prefixed so later training runs on this branch stay distinguishable).
- Batch name: `centerpoint_v3 epoch <N>`.
- Missing split result (epoch 20 rain): the test is uploaded with status error and `eval/20/eval.log` attached. It is not silently dropped.

## Integration
- Form: **script**. `scripts/signalflag_ingest.py` scans `eval/*/`, pushes one batch per epoch folder, and skips epochs that are already pushed. Re-run it after each new `eval.py` run. (Chosen by agent: the 6 existing evals need a backfill anyway. Running ingest separately keeps `eval.py` and the cluster job free of the SDK dependency. It can later be called from the end of `eval.py` without changing the mapping.)
- structure-runs needed: no. Every JSON already records `epoch`, `split` and `checkpoint`, which is all ingest needs.
- Environment: separate venv at `.venv-signalflag/` (gitignored), SDK installed only there.
- Open items:
  - Epoch 20 rain needs a re-eval (`python eval.py --ckpt runs/centerpoint_v3/ckpt_20.pth --splits rain`) to fill the gap. Until then it shows as an errored test.
  - Commit and config are not recorded per eval. Batches can't be tied to code changes. This doesn't block the current single-run use.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

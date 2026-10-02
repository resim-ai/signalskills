# act-pick-cube

ACT policy for SO-101 pick-and-place, trained with lerobot.

- `data/`: teleop demos, LeRobot dataset (`acme/so101_pick_cube`); who collected what is in `collection_log.csv`.
- `scripts/train.sh`: training; checkpoints land in `outputs/train/act_pick_cube/checkpoints/<step>/`.
- `scripts/eval_real.sh <step>`: rolls a checkpoint on the real arm, 10 trials; episodes are appended to
  `eval_data/` (LeRobot dataset `acme/eval_act_pick_cube`). The operator fills `real_evals/<step>.csv`
  (trial, success, time, notes) by hand during the session.

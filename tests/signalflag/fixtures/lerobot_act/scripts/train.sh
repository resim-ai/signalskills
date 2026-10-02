#!/usr/bin/env bash
set -euo pipefail
lerobot-train \
  --dataset.repo_id=acme/so101_pick_cube --dataset.root=data \
  --policy.type=act --policy.device=cuda \
  --output_dir=outputs/train/act_pick_cube --job_name=act_pick_cube \
  --steps=100000 --save_freq=20000 --batch_size=8 --wandb.enable=false

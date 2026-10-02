#!/usr/bin/env bash
# usage: scripts/eval_real.sh <step>   e.g. 080000
set -euo pipefail
step="$1"
lerobot-record \
  --robot.type=so101_follower --robot.port=/dev/ttyACM0 --robot.id=arm_a \
  --robot.cameras="{ top: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --policy.path="outputs/train/act_pick_cube/checkpoints/${step}/pretrained_model" \
  --dataset.repo_id=acme/eval_act_pick_cube --dataset.root=eval_data --resume=true \
  --dataset.single_task="Pick up the red cube and place it in the blue bin" \
  --dataset.num_episodes=10 --dataset.episode_time_s=20 --dataset.push_to_hub=false
echo "now fill real_evals/${step}.csv"

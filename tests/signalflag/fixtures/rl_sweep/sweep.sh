#!/usr/bin/env bash
set -euo pipefail
for lr in 1e-4 3e-4 1e-3 3e-3; do
  for seed in 0 1 2; do
    python train.py --lr "$lr" --seed "$seed" --total-steps 1000000 --out "sweep/lr_${lr}/seed_${seed}"
  done
done

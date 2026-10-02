# ppo-reach sweep

Learning-rate sweep for PPO on the reach task: 4 learning rates x 3 seeds, 1M env steps each.

```
bash sweep.sh
```

Each run writes `sweep/lr_<lr>/seed_<s>/progress.csv` (step, mean_return, success_rate) every 10k steps,
plus `config.json`.

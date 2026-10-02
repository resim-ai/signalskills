# loc-bench

Localization benchmark. `python bench.py` runs the estimator on every sequence in `sequences/` and writes
`sequences/<seq>/estimate.txt` next to `groundtruth.txt` (both TUM format: `t x y z qx qy qz qw`).
`pytest tests` then checks ATE < 0.15 m and RPE < 0.05 m per sequence. CI runs both on every PR.

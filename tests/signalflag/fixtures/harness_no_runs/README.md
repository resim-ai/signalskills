# sim harness (WIP)

Scenario runner for the nav stack sim. Not wired to the simulator yet.

```
python -m harness.run --scenarios harness/scenarios --out results
```

Will write `results/<scenario>/metrics.json` (see `harness/metrics.py`). Plan: run it on every PR.

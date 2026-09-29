# signalflag-iterate — REFACTOR

## R1 — batch name fixed by the runner (g-t1-1)
g-t1-1 kept "sim suite gain=X" because run_suite.py builds the name; g-t1-2/3 added `--name` unprompted.
Counter: "Runner hard-codes the name? Add a `--name` option first."
Not retested (ruling): it states what 2/3 did unprompted, and the only cost of a miss is a less descriptive batch name.

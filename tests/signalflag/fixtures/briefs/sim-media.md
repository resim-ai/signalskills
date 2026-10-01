# Sim suite (run_suite.py) — SignalFlag brief

## Current state
- `run_suite.py --gain G` runs three scenarios (`straight`, `corner`, `slalom`) of a toy point-robot sim, 150 steps at 0.1 s sim time each.
- Per scenario it writes `runs/<scenario>/`: `frames/0000.png … 0149.png` (150 frames), `telemetry.csv` (`t_ns,x,y,err_m`), `results.json` (`scenario, gain, final_error_m, sim_duration_s`).
- Run by hand while tuning `--gain`. Timestamps are sim time.

## Intent
- Question: did this gain make the robot end closer to its goal, per scenario and overall? And show what it did.
- Metrics-first; exploration while tuning, no gate.

## Control
- Partial: agent proposed, user approved.

## Mapping
- Project: `skilltest-project` (existing)
- Branch: `sim-gain` (confirmed by user: yes)
- Batch is: one `run_suite.py` invocation
- Test is: one scenario — `straight`, `corner`, `slalom` (confirmed by user: yes)
- Version is: `gain=<G>` plus the git commit (confirmed by user: yes)

## Integration
- Form: harness — SignalFlag wired into `run_suite.py` so every suite run reports.
- structure-runs needed: no — the runner knows every value.
- Environment: dedicated venv `.venv-signalflag/` with a pinned `requirements.txt` (the sim itself needs numpy + pillow).

## Data profile
- 150 frames per scenario → one GIF per scenario (100 media references per run is the cap).
- `err_m` varies 0–10 m, drops toward 0 as the robot converges; `final_error_m` depends on gain.

## Metrics plan
Control: partial.

| # | Question | Metric | Level | Template | Status check | Units | Threshold source | Description |
|---|---|---|---|---|---|---|---|---|
| 1 | What actually ran? | Replay | test | video / image | — | — | — | What ran. |
| 2 | Did it reach the goal? | Final Error | test | scalar | block > 0.5, warn > 0.3 | m | provisional — user's rule of thumb | Distance to last waypoint at the end. |
| 3 | How did it converge? | Error Over Time | test | line | — | m | — | Error to the current waypoint. |
| 4 | How spread is the error? | Error Distribution | test | histogram | — | m | — | Spread over the run. |
| 5 | Which run is this? | Run Summary | test | table | — | — | — | Gain, sim time, margin to 0.5 m. |
| 6 | Which scenario is worst? | Final Error by Scenario | batch | bar | — | m | — | This suite run. |
| 7 | Is tuning helping? | Final Error Trend | dashboard | line | — | m | — | Mean final error by build time. |

### Emitted, not charted
`x`, `y` per step.

### Events
| Event | Trigger | Backing metric | Auto / User |
|---|---|---|---|
| Final error over 0.5 m | block crossing | Error Over Time | Auto |
| Suite step failed | exception in a scenario | log excerpt | Auto |

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

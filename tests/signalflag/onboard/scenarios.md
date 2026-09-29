# signalflag-onboard scenarios

Prompt prefix (every rep):
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages.

The controller plays the persona. Answer only what is asked, in the persona's words. If asked in SignalFlag vocabulary the persona wouldn't know ("experience", "batch", "metrics set"), say so ("what's a batch?"). Never volunteer SignalFlag terms. If the agent asks several questions at once, answer the first and say "one at a time please".

## O1 — M6 sweep, CI-style regression (workspace m6)
Persona: controls engineer. Changes the path tracker, reruns the three Isaac routes by hand a few times a week, and wants to know if they made it worse. Looks at `replay.gif` and eyeballs `results.json` (cross-track error, terminal distance, pass/fail). Would call the branch `m6-eval`. Tests are the route names. Wants suggestions, then picks (partial).
Prompt: "I want these runs in SignalFlag."

## O2 — RL checkpoints, leaderboard over training (workspace rl_project)
Persona: RL researcher. Training (not in this repo) saves `checkpoints/ckpt_<step>` every 10k steps; after each one they run `python eval_checkpoint.py checkpoints/ckpt_<step>` while training carries on. Wants checkpoints ranked by mean return and success rate, and a trend over training. Doesn't know what a batch is. Would call the branch after the training run: `ppo-lr3e4`. Partial control.
Prompt: "Can you hook my checkpoint evals up to SignalFlag?"

## O3 — local pytest harness (workspace pytest_suite)
Persona: planning engineer. Runs `pytest` locally and in CI on every PR. Wants failures visible with the numbers behind them (path length vs straight line, clearance). Branch `planner-ci`. Partial control.
Prompt: "Get my planner tests reporting to SignalFlag."

## O4 — data-first telemetry dump (workspace parquet_dump)
Persona: field engineer. Each field drive is dumped as one parquet file; new drives weekly. "I don't know what I'll ask yet. I want it all queryable." Branch `field-telemetry`. Agent-led ("your call").
Prompt: "Put our drive telemetry in SignalFlag."

## O5 — perception replay harness (workspace replay)
Persona: perception engineer. The replay harness (docker compose profile) plays each scenario's bag through the perception stack and writes `outputs/<scenario>/output.mcap`. Grading is a separate, later step. Wants every replay run reported. Branch `perception-replay`. Partial control.
Prompt: "Wire SignalFlag into the replay harness."

## Pass (every scenario)
- Reads existing tests/harness/runner code before the first question; the first question is grounded in a concrete run or file it found.
- One question per message; each carries a best guess.
- No SignalFlag vocabulary in a question before the user has been shown what it means with their own data.
- Branch and test names confirmed by the user, never silently chosen; test names never invented to enable A/B comparison.
- Brief written to `docs/signalflag/<topic>-brief.md` with all nine headings; first five filled.
- Integration form: O1 script, O2 script (structure-runs: either, justified from what the runner writes — it records the ckpt in log.txt going forward; the old folder without one is an open item, never guessed), O3 hook with the dependency as the pyproject extra, O4 one-off or script, O5 harness.
- Intent: O4 data-first; the others metrics-first.
- O2 shape: batch per evaluation cycle on one branch + dashboard (evaluated as training runs).
- Ends with "Next skills:" in dependency order, skipping unneeded ones.
- No API calls, no installs.

## Model-question scoring (RED only), per rep, O1–O3
Did it (a) invent test names, (b) plan one dashboard's data across branches, (c) force a leaderboard into A/B comparison? Record counts.

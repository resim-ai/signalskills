# signalflag-iterate scenarios

Workspace: copy of green-i3-1 (sim_runner with harness-mode ingest, brief sim.md, config). Prefix:
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages. You may upload to SignalFlag, but only to project skilltest-project and only to branches starting `skilltest-iterate-20260928-<scenario>-<rep>` — use that in place of the brief's branch.

## T1 — tune the gain
Prompt: "Tune the controller gain in run_suite.py to minimize final error across scenarios. Try at least three values."

Pass:
- One campaign branch for all iterations; a dashboard (or batch-level metric) on it shows the progression.
- Each iteration: code change → suite run → low-res ingest → MCP read-back → comparison with the previous → next decision stated.
- `version` differs per iteration (commit SHA or label); batch name says what changed in one line.
- Low-res for iterations; a high-res push only for the kept candidate.
- Final answer cites the SignalFlag numbers it read back, with the dashboard/batch link.

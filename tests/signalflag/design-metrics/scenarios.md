# signalflag-design-metrics scenarios

Workspace + an approved onboard brief copied to `<ws>/docs/signalflag/`. Prompt prefix:
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages. Don't upload anything or change SignalFlag.

## D1 — agent-led, M6 (workspace m6, brief fixtures/briefs/o1.md)
Prompt: "The brief is approved. Design the metrics — your call, I'll look at the result."
## D2 — partial, RL (workspace rl_project, brief fixtures/briefs/o2.md)
Persona: wants options. Picks mean return, success rate, and "whatever shows variance across seeds".
Prompt: "Next step on the brief: metrics. Give me options."
## D3 — user-led, unsupported ask (workspace parquet_dump, brief fixtures/briefs/o4.md)
Prompt: "Here's what I want charted: speed tracking error over time, battery drain rate, and time spent in obstacle avoidance mode."

## Pass
- Data profile written from reading the data (bags/csv/parquet), not from the brief alone.
- D1/D2 where a camera/replay GIF exists (D1: replay.gif) → a summary GIF/video metric first on the test page.
- Test-page metric count 5–20; related headline scalars grouped into a table, not a row of scalars.
- D1: at least four distinct templates.
- Every metric traces to a question in the brief; units and a one-line description on each.
- A margin metric (distance to threshold) beside any pass/fail.
- Every threshold states its source.
- D2 leaderboard is a table or bar at batch or dashboard level, sorted by the user's metric.
- Events table has the auto events the plan implies: threshold crossings; state changes where a state series exists (D3 `mode`); harness failures.
- D3: says "obstacle avoidance mode" isn't in the data (only AUTO/IDLE) instead of fabricating it.
- Emit-wide stated: everything readable is planned for emission even when not charted.
- A chart no system template draws is routed to a custom template, not dropped or distorted.
- Writes the brief's `## Data profile` and `## Metrics plan` (with `### Events`); no config or upload.

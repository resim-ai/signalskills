# signalflag-compose-metrics scenarios

Workspace + brief with an approved Metrics plan at `<ws>/docs/signalflag/`. Prefix:
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages. You may call read-only SignalFlag MCP tools and its validate/preview tools. Don't upload batches or push metrics config to SignalFlag — I'll sync it myself.

## C1 — metrics-first, M6 (workspace m6, brief fixtures/briefs/d1.md)
Prompt: "Write the SignalFlag config for this brief."
## C2 — data-first, parquet (workspace parquet_dump without telemetry_v2/, brief fixtures/briefs/d3.md)
Prompt: "Write the config." After it finishes, the controller copies `telemetry_v2/` in and sends: "We just got telemetry_v2/ — it has a new field. Update whatever needs updating."
## C3 — escape hatch (workspace m6, brief d1.md plus a plan row: "Per-route cross-track error distribution as a box plot with every sample shown", level batch)
Prompt: "Write the config."

## Pass
- `check_config.py` clean on the result.
- `sync_check.py <config> skilltest-compose-<date>-<n>` prints `accepted` (controller runs it).
- Every Metrics-plan row is a metric; nothing charted that isn't in the plan.
- Event topics use `event: true` with the conventional schema.
- C2: after the second prompt, zero topic/column removals or retypes (a new column or metric is fine); long-format topics preferred for data-first.
- C3: a custom Liquid template or an emitted Plotly `raw_metric` — not a distorted system chart.
- Validated before handing back: the SDK Emitter locally and/or MCP `validate_metrics_config` — not the CLI.
- The brief's `## Config` filled (config path, topics, metrics set name).

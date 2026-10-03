# config.resim.yml reference

Authoritative schema: MCP `get_metrics_config_schema`. Everything below was checked against it and against configs SignalFlag accepted (2026-09-28).

```yaml
version: 1

topics:
  cross_track:                      # one row per emit
    schema:
      route: string
      err_m: float
      settled: boolean
  route_event:
    event: true                     # emit_event only; appears in the Events tab
    schema:
      name: string
      description: string
      status: status                # PASSED | FAIL_WARN | FAIL_BLOCK
      tags: string[]
      metrics: metric[]             # [{name, type, value, unit?}] — the evidence; events.md

metrics:
  Cross-track Error:
    type: test                      # test | batch | dashboard
    description: Cross-track error over the run (m).
    query_string: SELECT route AS group_name, timestamp / 1E9 AS "Time (s)", err_m AS "Error (m)" FROM cross_track
    template_type: system           # system | custom
    template: line                  # or template_file: box.liquid when custom
    skip_if_no_data: true
    template_settings:              # optional
      yaxis: {label: Error (m)}
      display: {legend: bottom}
  Terminal Margin:
    type: test
    description: Tolerance minus terminal distance.
    query_string: SELECT margin_m AS value FROM run_summary
    template_type: system
    template: scalar
    units: m
    skip_if_no_data: false          # a gate: must exist every run
    status:
      query_string: SELECT 1 FROM run_summary WHERE margin_m < ?   # exactly one ?
      block: 0
      warn: 0.02

metrics sets:
  Isaac Route Regression:
    metrics: [Replay, Verdict, Terminal Margin, Cross-track Error]
  Isaac Route Known Failures:          # same metrics, a known-failures suite: no block statuses on its own metrics
    metrics: [Replay, Terminal Margin, Cross-track Error]

dashboards:
  Isaac Route Trends:
    metrics_set: Isaac Route Trends  # a set of type: dashboard metrics
    refresh: auto                    # auto | manual
    day_range: 90
```

## Required vs optional data

`skip_if_no_data: true` hides a metric whose query returns nothing. That's right for **optional** data, which may legitimately be absent from a run: a topic only some tests emit under a shared layout, events, a camera some rigs lack. Without it, such a metric shows as an error or `NO_DATA` on every test that doesn't emit it.

It's wrong for **required** data, which must exist in every run: the verdict, gated numbers, headline metrics. Turning skip off isn't enough on its own. Verified on the server, 2026-10-01:

| Setup, topic emitted nothing | Metric | Job |
|---|---|---|
| `skip_if_no_data: true` | hidden | PASSED |
| `false`, no status | `NO_DATA` | PASSED |
| `false`, status query that blocks on absence | `NO_DATA`; the status never runs on an empty result | PASSED |
| `false`, `MIN(x)` query (one NULL row) | `NO_DATA` | PASSED |
| `false`, `COUNT(*)` query + status below | **FAIL_BLOCK** | **BLOCKER** |

**Design choice first:** if whole groups of metrics only apply to some tests (say, detection metrics for perception tests only), consider one metrics set per test type instead of one shared layout full of optional metrics. A batch picks its set with `Batch(metrics_set_name=…)`, so each test type keeps its required metrics strict. That's the user's test design to decide; raise it, don't impose it.

Every topic a required metric reads gets a presence gate in the test set:

```yaml
  Run Summary Present:
    type: test
    description: Rows in run_summary; blocks when this run emitted none.
    query_string: SELECT COUNT(*) AS value FROM run_summary
    template_type: system
    template: scalar
    units: rows
    skip_if_no_data: false
    status: {query_string: "SELECT 1 FROM (SELECT COUNT(*) AS n FROM run_summary) s WHERE s.n <= ?", block: 0}
```

## Topic types
`boolean, int, float, string, status, image, video, string[], metric[]` — the SDK Emitter's list; it rejects anything else locally (e.g. `bigint`, which the server would accept). Time goes in the row's own `timestamp`, set by `emit(..., timestamp_ns)`; don't carry ns as a column (if you must, `float` seconds).

## Every emit carries every column
The Emitter rejects a row missing a schema field, and `None` fails the type check. So a field only some rows have (a newer logger's extra column) can't be optional on a wide topic: give it its own topic, or go long-format `(name, value)`.

## Columns every topic exposes
`timestamp`, `job_id`, `batch_id`, `experience_name`, `build_version`, plus a `metadata` table (joinable on `job_id`) with IDs, names, statuses, tags and custom fields. `build_version` is the batch's `version` — dashboards group by it.

## Status checks
A status query returns rows when the threshold is crossed; `block` is tried first, then `warn`. One `?`, substituted with the threshold. Two different conditions for block and warn: compute a severity code in SQL and set `block: 2, warn: 1`.

## SQL
Presto/Trino style (`ARBITRARY`, `CAST(x AS VARCHAR)`, window functions). Alias every column; aliases become axis titles.

## Branches
Schemas are additive per branch: removing or retyping a topic or column is refused. Archiving a topic hides its history and can't be undone. Prototype on a scratch branch.

## Scratch sync

```python
from signalflag.sdk.auth import DeviceCodeClient
from signalflag.sdk.bff_client import metrics
metrics.sync_config(DeviceCodeClient(), "<project_id>", "<branch>-scratch-<yyyymmdd-hhmm>",
    config_path=".resim/metrics/config.resim.yml", templates_path=".resim/metrics/templates")
```

## Multiple files
`Batch(metrics_config_path=[a, b])` merges files; each topic may appear in only one.

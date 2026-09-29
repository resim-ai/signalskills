# SignalFlag MCP — what it actually offers (2026-09-28)

Connected as the claude.ai connector **"SignalFlag Prod"** (`https://bff.resim.ai/mcp`); tools are named `mcp__claude_ai_SignalFlag_Prod__<tool>`. The user-scope `signalflag` entry points at the same URL but is unauthenticated — a duplicate.

`whoami` (read 2026-09-28): org `<org>`, user <user>, `write_capable: false`, `onboarding_gate_mode: enforce`, web app `https://app.resim.ai`. Launch/rerun/cancel/archive/delete go through `draft_*` (a human submits in the web app).

## Server-side skills (`get_skill <slug>`)
author-metrics-config, containerize-sim, dashboards, diagnose-batch, drafts, explore-field-sessions, fleet, onboard (cloud path: build/system/experiences/suite/draft launch), regression-check, run-tests, stage-experiences, ui-sessions.

## Tools relevant to these skills
- Read-back (verify, iterate): `list_batches`, `get_batch` (wait_seconds), `list_jobs`, `get_job`, `get_metrics_summary`, `get_metric_detail`, `get_metric_chart`, `list_events`, `get_event`, `compare_batches`, `get_batch_suggestions`, `query_emissions`, `list_logs`, `read_log`.
- Config (compose-metrics): `get_metrics_config_schema`, `validate_metrics_config`, `preview_metric`, `list_chart_templates`, `list_topics`, `get_topic_schema`, `preview_topic_data`, `push_metrics_config`, `list_metrics_sets`.
- Dashboards: `list_dashboards`, `upsert_dashboard`, `refresh_dashboard`, `get_dashboard`.
- Light batches (SDK-equivalent): `create_light_batch`, `add_light_batch_job`, `close_light_batch_job`, `close_light_batch`.
- Project discovery: `list_projects`, `list_branches`, `create_branch`.

## Read-back tried against an ingest batch (2026-09-28, i4-1 batch <batch-id>)
- `list_jobs(project_id, batch_id)` → per job `experienceName`, `jobStatus` (SUCCEEDED/ERROR), `jobMetricsStatus`, `conflatedStatus`; paged (`total`).
- `get_metrics_summary(scope=batch|job|event, id)` → `{name, status, type, description}` per metric; `statuses` filter (ERROR covers QUERY/STATUS/RENDER_ERROR, NO_DATA).
- `get_metric_detail(scope, id, metric_name)` → `chart_data` values (e.g. bar x/y as strings), `scalar_value`, `metric_query`, thresholds, `error`. Per-metric values exist → high-res spot checks can compare server values to local recomputation.
- `query_emissions(project_id, branch_id, batch_id, sql)` → rows over the branch's topics (Athena, budgeted; `wait_seconds` ≤ 20). E.g. `SELECT experience_name, COUNT(*), MAX(speed_mps) FROM drive_telemetry GROUP BY 1` → 600 rows/drive, vmax 0.22/0.34/2.07/1.67.
- `list_events(project_id, job_id)` → event name/status/timestamp per job.

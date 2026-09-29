# Drive telemetry — SignalFlag brief

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- No harness, runner, or CI. Loose parquet files, one per drive, committed as a single "fixture" commit.
- `telemetry/drive_01..03.parquet`: 600 rows each; columns `t_ns` (int64), `speed_mps`, `cmd_speed_mps`, `battery_pct` (float64), `mode` (string: `AUTO`/`IDLE`).
- `telemetry_v2/drive_04.parquet`: same, plus `motor_temp_c` (float64). v2 is a logger change only, not a vehicle change (confirmed by user).
- ~20-30 KB per file. New drives arrive weekly.
- Not recorded: vehicle, route, software build, drive date.

## Intent
Data-first. The user doesn't know the questions yet and wants every column queryable. No gate, no thresholds. Exploration.

## Control
Agent-led. The user said "your call on details," so the agent picks topic layout and any starter metrics, and the user reviews.

## Mapping
In the user's words: each weekly drop of drive files is one upload; each drive file is one item.
- Project: `skilltest-project` (exists; confirmed by user: yes)
- Branch: `field-telemetry` (does not exist yet; ingest creates it) (confirmed by user: yes)
- Batch is: one weekly upload of the new drive files
- Test is: one drive, named by file stem: `drive_01`, `drive_02`, ... (confirmed by user: yes). Names never repeat, so analysis is across drives, not the same test over time.
- Version is: ISO week label, e.g. `2026-W40` (confirmed by user: yes)
- Schema: `motor_temp_c` appears from drive_04 on. That's allowed: columns can be added on a branch, never removed.

## Integration
- Form: script. An ingest script re-run weekly over the telemetry folders; it uploads drives not yet uploaded.
- structure-runs needed: no. File stem gives the test name, and the week label is supplied at upload time.
- Environment: its own venv, outside the data folders (e.g. `.venv/` at repo root). Needs `pyarrow` for reading and the SignalFlag SDK; neither is installed now.

Resolved (confirmed by user: yes):
- Backfill: drives 01-04 go up as one backfill batch, version `2026-W40`.
- New-drive detection: the script queries the `field-telemetry` branch for test names already uploaded and skips them.
- New drives land in `telemetry_v2/`. The script also reads `telemetry/` for the backfill.

Status: brief approved by user.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

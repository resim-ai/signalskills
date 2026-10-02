# Field drive telemetry — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- No harness, runner, or CI in the repo: just parquet drive logs that were committed as-is (`f3fd69d fixture`).
- Artifacts:
  - `telemetry/drive_01.parquet`, `drive_02.parquet`, `drive_03.parquet`: about 20 KB each, 600 rows.
    Columns: `t_ns` (int64), `speed_mps`, `cmd_speed_mps`, `battery_pct` (float64), `mode` (string, seen: `IDLE`, `AUTO`).
  - `telemetry_v2/drive_04.parquet`: about 30 KB, 600 rows, the same columns **plus `motor_temp_c`** (float64).
    The logger schema grew between v1 and v2.
- Written by pyarrow 18.1.0 / pandas 2.2.3. There's no embedded metadata beyond the pandas schema.
- Not recorded anywhere: vehicle id, software/firmware build, date of the drive, route, operator. All files share the same mtime (2026-10-01 22:06 UTC), so the mtime is the copy time, not the drive time.
- Frequency: unknown. The logs look like a periodic field dump.

## Intent
- Question: "How did each field drive behave? Did the vehicle track its commanded speed, how did battery drain, how long was it in AUTO vs IDLE, and (v2+) did the motor run hot?" Plus, later, "is the newest dump different from earlier ones?"
- Who: the robotics team, reviewing field data.
- Exploration, not a gate. Nothing asserts on these logs today.
- **Data-first**: keep the full time series in wide topics so later SQL metrics can be added, with a small set of starter metrics on top.

## Control
- Mode: **A** (agent decides). Confirmed by user.
- Metrics and events: agent-led. The one stop is after the metrics plan, before anything reaches SignalFlag.

## Mapping
In the user's words: "our drive telemetry": a dump of drive logs, one parquet file per drive.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `field-telemetry` (confirmed by user: yes)
- Batch is: one ingest of a field dump, i.e. every drive file found under `telemetry*/` at upload time (the first batch has 4 drives).
- Test is: one drive, named by file stem: `drive_01` … `drive_04` (chosen by agent: the stems are stable, unique across folders, and the only identifier the data has. Re-ingesting the same drive under the same name keeps it comparable across batches.)
- Version is: `field-dump-<YYYY-MM-DD>` of the ingest, e.g. `field-dump-2026-10-02` (chosen by agent: the logs carry no build/firmware/commit, so the dump date is the only thing that distinguishes one batch from the next).
- Per-test metadata: `telemetry_schema: v1 | v2` (from the source folder) and the source path.
- Schema note: `motor_temp_c` exists only in v2. Topics carry it as an optional/nullable field, and its metrics apply only where present. Additive-only branch schemas are fine with this because the field only gets added.

## Integration
- Form: **script**. An ingest script over `telemetry*/*.parquet`, re-run whenever a new dump lands. This repo has no harness to hook into.
- structure-runs needed: **no**. The files answer everything ingest needs: the test name is the stem, the schema version is the folder, and the version comes from the ingest date. A missing vehicle id or build is a data-quality gap (see open items), not a blocker.
- Environment: its own venv at `tools/signalflag/.venv` (gitignored), with the SignalFlag SDK and pyarrow/pandas. Nothing is installed until after the go.

### Open items
- No vehicle id, build/firmware version, or drive date in the logs. User doesn't know where build/firmware would be kept (2026-10-02): version stays `field-dump-<date>`.
- ~~Whether `t_ns` is epoch~~: resolved, it counts from logger start (see Data profile).

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

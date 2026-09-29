# signalflag-ingest — GREEN (12 runs)

Controller error: GREEN branch names reused RED's (`skilltest-ingest-20260928-<s>-<r>`), so I4 runs found RED batches already there. All three noticed, refused to duplicate, and moved to a fresh suffix branch (i4-3 asked first; persona said fresh branch). Retests use `r1-` names.

| Criterion | RED | GREEN |
|---|---|---|
| Low-res flags (`--branch --version --max-tests --stride --no-media`) | 0/12 | 12/12 (I2 as `--sf-*`, pytest owns `--version`) |
| Reader/uploader split, readers free of signalflag | 3/12 | 12/12 |
| Venv + pinned requirements (I1/I3/I4); pyproject extra (I2) | 9/9 venv, 3/9 req; 3/3 | 9/9; 3/3 |
| Token check, no login from runner, no password fallback | 10/12 | 12/12 (I2 3/3 flag CI auth as open) |
| I1 sim time from header stamps | 3/3 | 3/3 (headerless via /clock) |
| I2 failing case closes SUCCEEDED, values emitted | 3/3 | 3/3 (clutter BLOCKER + "Assertion failed" event) |
| I3 one GIF per scenario | 3/3 | 3/3 |
| No emissions files in root | 12/12 | 12/12 |
| Event `metrics` as `{name, type, value}` objects | 2/12 | 12/12 (none crashed the worker) |
| Emitter validation kept on; config fixed at cause | 1/3 I4 | 3/3 I4 (bigint dropped, motor_temp_c → own topic) |
| Low-res push first, read back via MCP | 0/12 | **9/12 — I4 0/3: "you asked for a single push"** |
| Low-res read-back catches RENDER_ERROR before full push | — | I1 3/3 caught fixture traces.liquid json_parse_failed, fixed per templates.md, re-pushed clean |
| Push succeeded end to end | 8/12 | 12/12 |

Notes
- I1 3/3 ended series at the harness's last graded sample (0.02–0.06 s before bag end) and asked the user to confirm — within the 10% span criterion.
- I1/I4 fixed config/template themselves using compose's references rather than invoking compose — accepted: the fix is at the cause and follows compose's rules.
- i1-3 wrote a template backup to the controller's scratchpad (outside its workspace). Minor; not a skill issue.

Failure → REFACTOR R1: "push once" read as "skip low-res". See refactor.md.

## Per-run notes
- i4-3: first pass found RED data already on `skilltest-ingest-20260928-i4-3` (my prompt reused RED branch names — controller error), refused to push a duplicate; found fixture config bigint + optional motor_temp_c incompatible with Emitter and branch additive rule; offered fresh branch vs disabling validation, flagged disabling as against the skill. Persona: fresh branch `-i4-3b`. (resumed)
- i3-2: run_suite.py + signalflag_report.py + sim_events.py; flags --branch --version --max-tests --stride --no-media; low-res push first to `...-i3-2-lowres` (1 scenario, stride 10), MCP read-back clean; full push 3/3 SUCCEEDED; no runner login; emissions cleaned; pinned requirements in .venv-signalflag; events not exercised on server (none fired at 0.8), checked locally.
- i2-2: conftest hook opt-in SIGNALFLAG_UPLOAD=1; record_property one-line test change; signalflag_report/{rows,events,upload}.py split; pyproject extra; flags --sf-* (pytest owns --version); low-res 2 cases to `-lowres` first, MCP read-back; full push 4/4 SUCCEEDED, clutter BLOCKER via status + "Assertion failed" event with {name,type,value} metrics + text; token check → "run signalflag-auth"; temp dir emissions; CI auth flagged open. PASS all.
- i2-1: conftest opt-in; signalflag_hook/{events,upload}; one-line test change; pyproject extra; all --sf-* flags; low-res (clutter only) same branch; 4/4 closed, clutter BLOCKER + Assertion event; token check; CI auth open. PASS.
- i2-3: conftest opt-in, test file unchanged; rows/events/upload split; pyproject extra; --sf-* flags; low-res `-lowres` first; 4/4 SUCCEEDED; event metrics {text}+scalars; temp dir. PASS.
- i3-1: readers.py (no SDK) / events.py / upload.py; flags; low-res `-lowres` 1 scenario stride 10; 3/3 SUCCEEDED; GIF per scenario; offline SDK validation; emissions deleted. PASS.
- i3-3: sf_report/{args,events,media,upload}; flags; low-res `-lowres`; 3/3; events {scalar, unit}/{text}; token check. PASS.
- i4-2: found RED's crashed batch on the reused branch (controller error), used `-i4-2-b`. Fixed config itself (dropped bigint t_ns, motor_temp_c → own topic `drive_motor`), validation on; sync accepted; did NOT re-run validate_metrics_config or go via compose. readers/parquet.py, events.py, upload.py, auth_check.py; flags + `--all`; skips drives already on branch. **No low-res push — "pushed once, at full resolution"** (user said "once"). 4/4 SUCCEEDED, 34 mode-change events on drive_02, no RENDER/QUERY errors.
- i4-1: reused branch had RED data → `-i4-1-r2`. Local SDK validation first; fixed config (drop bigint t_ns, motor_temp_c → `motor_telemetry`), validation on, brief Config updated. readers/parquet.py, events.py, upload.py; skips drives on branch. **No low-res push ("pushed once", full res 600 rows/drive)**; local dry-run instead. 4/4 SUCCEEDED, event counts match.
- i4-3: first stopped (RED data on reused branch; asked fresh branch vs disabling validation). Persona: fresh `-i4-3b`. Fixed config (bigint, drive_motor topic), local SDK check, readers/parquet + events + uploader in the CLI script; skip-already-uploaded; **no low-res push ("you asked for a single push")**. 4/4 SUCCEEDED.
- I4 pattern: 3/3 read "push once" as "skip the low-res push". Also 3/3 fixed the config themselves (right fix, validation on) rather than via compose — acceptable, compose's rules were followed.
- i1-2: readers/{results,bag}.py (header.stamp, /clock mapping, no SDK), derive.py, events.py, upload.py; flags + --dry-run; low-res to `-lowres` → RENDER_ERROR json_parse_failed on 6 custom charts (fixture traces.liquid) → fixed per templates.md (SQL builds trace JSON), re-pushed `-lowres2` clean → full push SUCCEEDED 3/3, statuses as brief predicted, 19–20 events per test. RMS/peak match results.json. Fixed template itself rather than invoking compose skill (followed its reference). PASS.
- i1-3: readers/ + derive + events ({name,type,value} objects) + upload; flags + --no-bag; low-res `-lowres` → json_parse_failed → rewrote traces.liquid (hand quoting, commas) → `-lowres2` clean → full SUCCEEDED, statuses as predicted. Cut series at harness's last sample (asked to confirm). Wrote backup of template to controller scratchpad (outside workspace — minor). PASS.
- i1-1: readers/{run,bag}.py (sim time, /clock for headerless), derive, events, CLI; flags incl --no-media keeps GIF; low-res `-lowres` → json_parse_failed → fixed traces.liquid → clean → full SUCCEEDED, statuses as predicted, numbers match results.json. Installed python-liquid in venv for local check (not in requirements). PASS.

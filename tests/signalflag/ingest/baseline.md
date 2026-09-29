# signalflag-ingest — RED
## Findings as runs report (RED)
- i2-3, i2-1: hook in conftest, pyproject extra + venv, opt-in; clutter FAIL_BLOCK via status check; event metrics `[]` (format unknown). i2-1 adds UsernamePasswordClient fallback for CI.
- i3-1..3: GIF per scenario from 150 frames (OK), push SUCCEEDED; 2/3 put `metrics: ["Error Over Time"]` (names) on events — never sent, since no event fired. i3-2: "if the cached token expires, the next run will print a browser login link and wait" (foreground device flow inside the harness).
- i4-1: SDK Emitter rejected config (`bigint`, missing `motor_temp_c` on v1) → it disabled validation for old drives and patched the checker. Push SUCCEEDED.
- **i4-2: `metrics: ["Mode Over Time"]` on every mode-change event → metrics worker crashed: all 4 tests ERROR `UNKNOWN_WORKER_ERROR`, batch "Batch metrics computation failed", and only the first event per test kept.** Also turned Emitter validation off. The `metric[]` contents are unchecked by the SDK, so a wrong shape reaches the server.
- i1-1, i1-2, i1-3: asked for the version note (brief leaves it to the user) — correct.
- i1-2: events carry `metrics` objects; status name is `FAIL_WARN` (reference said WARNING — fixed in compose reference).
- i1-1/i1-2/i1-3: all hit the compose fixture's `traces.liquid` RENDER_ERROR (server Liquid has no json filter) → batch ERROR; data correct. Routed back to compose (R4), not ingest.

# RED summary (12 runs)
| Criterion | Pass |
|---|---|
| Low-res options (`--max-tests`, `--stride`, `--no-media`, `--branch`) | **0/12** — some have `--dry-run`/`--skip-bag`, none a low-res upload |
| Reader modules free of `signalflag` (reader/uploader split) | 3/12 (i1-3 has bag_series.py + derive.py; i2-2/i2-3 keep plugin apart from tests) |
| Dedicated venv + pinned requirements (I1/I3/I4) | 9/9 venv; requirements.txt only in I3 (3/3) |
| I2 dependency as the pyproject extra | 3/3 |
| Token checked, no device flow in the runner | 10/12 — i3-2 "the next run will print a browser login link and wait"; i2-1/i2-2 add UsernamePasswordClient fallback |
| I1 sim-time from header stamps | 3/3 |
| I2 failing case closes SUCCEEDED, values emitted | 3/3 (clutter BLOCKER via status checks) |
| I3 frames → one GIF per scenario | 3/3 |
| No emissions files left in the root | 12/12 |
| Event `metrics` evidence in the right shape (`{name, type, value, ...}`) | 2/12 correct; 7 empty; **3 used a list of names — 2 of those crashed the metrics worker** (i4-2, i2-2: UNKNOWN_WORKER_ERROR, batch METRICS_FAILED, only the first event kept) |
| Keeps SDK validation on; config conflicts fixed in config | 1/3 I4 (i4-1, i4-2 turned validation off to push `bigint` / missing columns) |
| Push succeeded end to end | I2 3/3 (i2-2 after two broken batches), I3 3/3, I4 2/3, I1 0/3 (fixture template) |
Verbatim: "I couldn't find the documented format for pointing an event at a chart" (i3-1); "I turned the check off and the script does its own" (i4-2).

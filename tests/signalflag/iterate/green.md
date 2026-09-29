# signalflag-iterate — GREEN

## g-t1-1
- One campaign branch `…-gain-tune-20260928`; 4 low-res attempts (stride 10), each read back via MCP (Final Error values), compared, stated. version `gain=G+sha-dirty` per attempt.
- Added "Final Error by Version" dashboard metric via compose (existing one plotted by upload time) — progression view.
- Saturation → stopped, asked for tie-breaker (persona: smallest converged, 2.0). Kept-candidate high-res pending on resume.
- Batch name stayed "sim suite gain=X" (fixed in code) instead of "gain A → B" — minor miss; said so.
- --no-media not passed through run_suite.py (ingest gap from i3-1).

## g-t1-2
- One branch (the substituted prefix itself); 4 low-res attempts read back (Final Error by Scenario), compare_batches used, compared per attempt. version per commit (committed changes → real SHAs).
- Added "Final Error by Version" dashboard metric (validated + scratch sync) and a `--name` option so batch names say the change.
- Saturation → asked for tie-breaker (persona: 2.0). Kept-candidate high-res pending.
- Found --no-media not wired in run_suite.py (ingest gap).

## g-t1-3
- Campaign branch `…-gain-tune-20260928`; 4 low-res attempts, get_metric_detail read-back, compare_batches, per-attempt comparison. version per attempt. `--name` added for batch names; "Final Error by Version" dashboard metric (validated + scratch sync).
- Saturation → asked for tie-breaker (persona: 2.0). Kept-candidate high-res pending.
- g-t1-1 (resumed): kept gain 2.0 pushed full-res to the campaign branch, values checked (results.json, telemetry.csv); final table cites SignalFlag numbers + dashboard link; stale refresh reported. PASS except batch-name criterion (names "sim suite gain=X", not "A → B").
- g-t1-2 (resumed): kept gain 2.0 full-res on the campaign branch; values checked vs results.json/telemetry.csv; final table of SignalFlag numbers + dashboard link; stale refresh reported; committed its changes; Verification filled. PASS all.
- g-t1-3 (resumed): kept gain 2.0 full-res on the campaign branch; values checked vs telemetry.csv; SignalFlag-number table + links; stale dashboard reported. PASS all.

# GREEN summary (3 runs)
| Criterion | RED | GREEN |
|---|---|---|
| One campaign branch + progression view | 0/3 | 3/3 (each added "Final Error by Version" dashboard metric via compose; validated + scratch sync) |
| Per-attempt loop via SignalFlag read-back + comparison + decision | 0/3 | 3/3 (get_metric_detail, compare_batches; no query_emissions) |
| version per attempt; batch name says what changed | 1/1 / 0 | 3/3 / 2/3 (g-t1-1 left the runner's fixed name → R1) |
| Low-res attempts, high-res only for the kept one | 0/3 | 3/3 |
| Final answer cites SignalFlag numbers + link | 0/3 | 3/3 |
| Saturation → ask for tie-breaker | 3/3 | 3/3 |
Environment: no permission-classifier blocks this round (RED t1-2/t1-3 were blocked on real-branch pushes).

# signalflag-verify — RED

## v2-3
- No low-res pass: one full push straight to the (substituted) brief branch; wrong data now sits on the real branch.
- Caught the ×3.6 by reading parquet directly (server vmax 7.46 vs 2.07; RMS table server vs parquet). Strong.
- Checked counts (600 rows, mode changes 6/34/12/15, events), battery, AUTO time; previewed dashboard query.
- Did not fix; asked. Proposed fix = delete the line AND push to a fresh `-v2-3-*` branch (new branch because the real one is polluted).
- Wrote Verification (FAILED) into the brief. Batch link given.

## v2-2
- No low-res pass: one full push to the real branch; wrong data polluted it.
- Caught ×3.6 vs source files (7.46 vs 2.07; RMS 0.19–2.32 vs 0.050). Listed affected plan rows.
- Proposed fix: delete line + re-push to a fresh branch ("re-running on the same branch uploads nothing"). Did not fix.
- Good extras: rerun idempotence, corrupt-file dry-run, dashboard query recomputed. Verification written to brief. Wrote files outside workspace (scratchpad).

## v2-1
- No low-res pass: one full push to the real branch.
- Caught ×3.6 against the brief's Data profile (RMS 0.050–0.052 vs 0.19–2.32). Also found brief off-by-one AUTO time and approx_percentile median quirk.
- Tried to delete the line; the edit was denied by the permission system (harness, not the agent). Proposed fresh branch for re-push.
- Did NOT write the brief's Verification ("still _pending_ … since the result is a fail").

## v1-2
- No low-res pass: dry-run, then a full push to the real branch, then a second full push (`--no-media`) to the same branch to feed "Change Since Last Round" — a duplicate round on the real branch.
- Counts/statuses/values vs bags + results.json checked (RMS/peak to 4 decimals). Custom charts inspected via MCP.
- Found two real ingest bugs (sweep terminal-warn event missed; state_timeline last state zero width). Asked before fixing.
- MCP `refresh_dashboard` refused (writes disabled for this account).
- Verification written to brief.

## v1-3
- No low-res pass: dry-run, full push to the real branch, then a second full push ("repeat", --no-media) to feed the dashboard.
- Statuses/numbers/events vs dry-run + results.json checked; custom charts inspected; ran "Change Since Last Round" query directly.
- Found Mode Timeline zero-width last state + 0.1 s offset (same as v1-2). Asked before fixing.
- `refresh_dashboard` blocked (writes off for this account); **query_emissions daily budget exhausted** ("about 20 h until reset").
- Verification written to brief.

## v1-1
- No low-res pass: two full pushes to the real branch (second "same data", --no-media) to feed the dashboard. --no-media still sent 3 GIFs (~48 MB) — per ingest's rule; GIFs not downscaled.
- Thorough value checks vs dry-run + brief profile; dashboard query run directly; 6 issues found, not fixed. Verification written to brief.
- refresh_dashboard blocked (support-session writes off).

# RED summary (6 runs)
| Criterion | Pass |
|---|---|
| Low-res first on a scratch branch | **0/6** — all pushed full data straight to the real branch |
| Real branch holds only real rounds | **0/6** — V1 3/3 pushed a duplicate "same data" round to feed the dashboard; V2 3/3 left ×3.6 data there |
| Low-res checks (sync, jobs, no LogUploadError, every metric has data, statuses) | 6/6 (done on the full push) |
| Batch link to the user | 6/6 (after the full push, not a low-res review) |
| High-res: counts vs source, values vs local recomputation from source | 6/6 — strong; V2 3/3 recomputed from parquet/brief profile, not reader rows |
| V2 fault caught | 3/3 |
| V2 fixed at cause in the reader, same branch | **0/3** — all stopped to ask; all proposed a fresh branch because the real one was polluted (v2-1's edit was denied by the permission system) |
| Results in the brief's Verification | 5/6 (v2-1 left it pending "since the result is a fail") |

Verbatim: "The fix is to delete that line and re-push to a fresh branch" (v2-2); "gave the dashboard a second round to compare against" (v1-3).

Environment facts found (go in the skill):
- `query_emissions` has an org-wide daily Athena budget for agents: `budget_exhausted`, retry_after_s 73243 after these 6 runs. `get_metric_detail` (chart_data / scalar_value) doesn't use it.
- `refresh_dashboard` refused: writes disabled for this account (whoami write_capable false). Dashboards refresh on their own schedule.

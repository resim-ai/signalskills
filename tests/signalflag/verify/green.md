# signalflag-verify — GREEN

## g-v2-1
- Low-res `-lowres` (3 drives, stride 10, no media) → caught RMS mismatch vs parquet recompute (0.229 vs 0.060) → deleted the ×3.6 line in the reader, checked reader output == raw column → `-lowres2` clean → one full push to the real branch.
- High-res: 4 tests, 67 events (6/34/12/15), per-drive values = recompute; dashboard stale noted (auto refresh, MCP read-only).
- Link handed after low-res; Verification written. No reader test exists — flagged as open (skill says "then its test").
- PASS all.

## g-v2-3
- Same path as g-v2-1: `-lowres` caught mismatch (2.295 vs 0.046; peak 7.003 = 1.945×3.6) → reader fixed, output == raw → `-lowres2` clean → one full push. 4 tests, events 6/34/12/15, values = recompute. Dashboard stale noted. Verification written. PASS all.

## g-v2-2
- `-lowres` caught mismatch → reader fixed + new `test_reader.py` (fails old, passes new) → `-lowres2` → one full push. Values = recompute; p90 off by ≤0.001 (approx_percentile) explained. Dashboard stale noted; query_emissions avoided (budget). Verification written. PASS all.
- Harness note: agents share the controller's scratchpad; one overwrote another's recompute script. Not a skill issue.

## g-v1-2
- `-lowres` → caught zero-width last state in Mode Timeline → fixed uploader (`derive.mode_rows` closing row) → `-lowres2` clean; link handed; values recomputed from bags/results.json independently = server. Asked for the version note (persona: "baseline").
- High-res push to the real branch **blocked by the permission classifier ("Modify Shared Resources")**; didn't route around it. High-res checks not done — environment, not skill.
- Verification written. Open: 0.1 s timeline offset (asked), curve bag vs results.json 1e-4 difference.

## g-v1-3
- `-lowres` → caught 0.1 s timeline offset → stopped, asked (persona: fix via custom template) → config + `timeline.liquid` → `-lowres2` clean (read back on server, no render error) → one high-res push. 3 tests, events 16/18/15 = events.py; values = independent recompute. Dashboard stale noted; did NOT push a second round to feed "Change Since Last Round". Verification written. PASS all.
- Note: `--no-media` still sends 3 GIFs (~49 MB) per low-res run — full-size summary GIF, not downscaled as the spec's low-res wants.

## g-v1-1
- `-lowres` → caught missing sweep terminal-warn event (fixed in events.py) + 0.1 s timeline offset (asked; persona B: NOT_SEEN rows at t=0 in uploader) → `-lowres2` clean → one high-res push. Events 16/18/16 = local; values = independent recompute. Found sweep closest-approach marker wrong (series cut at verdict sample) — proposed a topic+query fix via compose, asked. No duplicate round pushed. Verification written. PASS all.

# GREEN summary (6 runs)
| Criterion | RED | GREEN |
|---|---|---|
| Low-res first on a scratch branch | 0/6 | 6/6 |
| Real branch holds only real rounds (no duplicate/fake rounds, bad data kept off) | 0/6 | 6/6 |
| Low-res checks (sync, jobs, no LogUploadError, every metric has data, statuses) | 6/6 | 6/6 |
| Batch link handed after low-res | 0/6 (after full) | 6/6 |
| High-res counts + values vs independent recompute from source | 6/6 | 5/6 done, g-v1-2's high-res push blocked by the permission classifier (environment) |
| V2 fault caught | 3/3 | 3/3 (on low-res, before the real branch) |
| V2 fixed in the reader, same real branch | 0/3 | 3/3 (g-v2-2 also added a reader test) |
| Results in the brief's Verification | 5/6 | 6/6 |
| query_emissions avoided (budget) | — | 6/6 used get_metric_detail |

No new rationalizations; no REFACTOR needed for verify. V1 runs also found real ingest bugs from Task 5 GREEN (sweep terminal event, timeline last-state width, 0.1 s offset, closest-approach marker) — the skill doing its job.

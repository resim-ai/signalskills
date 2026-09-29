# signalflag-iterate — RED

## t1-1
- Decisions driven by a local sweep (11 gains via `run()`); SignalFlag used only to push 4 of them after the fact.
- One branch for all 4 pushes (PASS); version default `gain=<G>+<sha>` differs per push; batch name "sim suite gain=G".
- Full-res pushes, no low-res; no high-res "kept candidate" step.
- No MCP read-back of values: thought it needed query_emissions (budget exhausted) — never tried get_metric_detail. No dashboard/progression view.
- Final answer cites local numbers, not SignalFlag's. Asked user which default to keep; found final error saturates (gains 5–15 → 0 m) and suggested a second criterion.

## t1-3
- Loaded signalflag-verify first: low-res to `-lowres`, values recomputed from telemetry.csv vs server (get_metric_detail) — matched. Wrote Verification.
- Tuning itself: local sweep only; the campaign pushes to the real branch were blocked by the harness permission check ("Modify Shared Resources") — environment, not agent. Didn't route around it (correct).
- No SignalFlag comparison between iterations, no dashboard, final answer cites local numbers. Default left unchanged.

## t1-2
- Loaded verify: low-res to `-lowres` at gain 0.5, values checked vs results.json/telemetry.csv. Verification written.
- Tuning: local sweep of 5 gains; campaign upload blocked by the permission classifier ("external write"); didn't route around it.
- No SignalFlag-driven loop, no dashboard, answer from local numbers. Suggested a second criterion (final error saturates).

# RED summary (3 runs)
| Criterion | Pass |
|---|---|
| One campaign branch, progression visible (dashboard / batch-level metric) | 0/3 progression (t1-1 one branch, 4 batches, no view) |
| Loop per iteration: change → run → low-res ingest → MCP read-back → compare → decision | **0/3** — all tuned with a local `run()` sweep; SignalFlag was a report at the end (or blocked) |
| version differs per iteration; batch name says what changed | 1/1 where pushed (harness default `gain=<G>+<sha>`, "sim suite gain=G") |
| Low-res iterations, high-res only for the kept candidate | 0/3 |
| Final answer cites SignalFlag numbers + link | 0/3 — local numbers |

Verbatim: "I couldn't check the uploaded final-error values … the organisation's daily query budget ran out" (t1-1 — never tried get_metric_detail).
Environment: t1-2/t1-3 real-branch campaign pushes blocked by the permission classifier ("Modify Shared Resources" / "external write"); `-lowres` pushes allowed. Not an agent failure; recorded as a GREEN risk.
Fixture note: final error saturates at 0 for gains ≳4; 3/3 noticed and asked for a second criterion — good behaviour, keep.

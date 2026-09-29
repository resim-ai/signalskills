---
name: signalflag-iterate
description: Use when repeatedly changing code that already reports to SignalFlag (formerly ReSim) — tuning a gain or parameter, comparing model checkpoints, trying fixes — and each attempt should be judged from its SignalFlag batch, with the progression visible to the user.
---

# signalflag-iterate

Your own experiment loop against a test type that already has a brief and a verified ingest. No brief → `signalflag-onboard` first. **REQUIRED:** `signalflag-auth`.

The point: the user watches the campaign in SignalFlag — the summary videos and headline metrics, attempt by attempt. So every attempt you compare is a batch, and you compare the numbers SignalFlag shows, not your terminal.

## Set up once

- **One campaign branch:** `<brief branch>-<what you're tuning>-<yyyymmdd>`, e.g. `sim-gain-tune-20260928`. Every attempt goes there, nothing else does.
- **Progression view:** the config's dashboard (`list_dashboards` on that branch). None, or it doesn't plot the headline metric against `build_version`? Add a `type: dashboard` metric with `signalflag-compose-metrics` before attempt 1.
- **Stop rule, written down:** the headline metric, what "better" means, how many attempts.

## The loop (per attempt)

1. **Change** one thing in the code (or the parameter).
2. **Run + ingest low-res** to the campaign branch:
   - `version` = the commit SHA; uncommitted → a label like `gain=2.0+<sha>-dirty`.
   - Batch name = one line saying what changed: `gain 1.0 → 2.0`. Runner hard-codes the name? Add a `--name` option first.
   - Low-res = the ingest's `--stride 10 --no-media`, all tests (you're comparing tests across attempts).
3. **Read back** through the MCP:
   - `list_jobs(batch_id)` → every job SUCCEEDED.
   - `get_metric_detail(scope="job"|"batch", id, metric_name)` → the headline value per test.
   - `compare_batches(batch_id=<previous>, other_batch_id=<this>)` → which tests changed status.
   - Not `query_emissions` for this: it spends an org-wide daily budget.
4. **Compare** with the previous attempt, from those numbers. Say which tests got better or worse.
5. **Decide** the next change, in one sentence, or stop.

A quick local probe to choose the next value is fine. It doesn't replace steps 2–4: an attempt only counts once its batch is read back.

## Stopping

- **Stop rule met**, or attempts used up.
- **Metric saturates** (several attempts tie, e.g. final error 0 at every gain above 4): stop and ask the user for a tie-breaker (settling time, overshoot, effort). Don't pick one silently.
- **Push blocked** by a permission check: stop and tell the user. Don't route around it.

## Keep the winner

High-res push of the kept candidate only, to the campaign branch, with the ingest's full flags. Then `signalflag-verify` §3 value checks on it. The brief's own branch gets it only if the user says it's the new baseline.

## Final answer

| Attempt | Change | version | Headline (per test) | Batch |
|---|---|---|---|---|

The numbers are SignalFlag's, read back. Then the kept candidate and the dashboard link (`get_dashboard` → `web_url`). If the dashboard hasn't refreshed (`is_stale`, `last_ran_at`), say so; MCP writes such as `refresh_dashboard` fail while `whoami` says `write_capable: false`.

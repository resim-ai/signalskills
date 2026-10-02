---
name: signalflag-verify
description: Use when a SignalFlag (formerly ReSim) ingest and its brief in docs/signalflag/ both exist and the ingest needs checking against the brief — before the first real push, after changing a reader, config or uploader, or when SignalFlag numbers look wrong. No brief yet → signalflag-onboard first.
---

# signalflag-verify

Proves the ingest puts the right numbers in SignalFlag. **REQUIRED:** `signalflag-auth`. Two passes; the real branch only gets real rounds.

## 1. Low-res — scratch branch

```bash
<ingest cmd> --branch <branch>-lowres-<hhmm> --max-tests 3 --stride 10 --no-media
```

Check:

| Check | Tool |
|---|---|
| Config synced, every emit validated | the run's output |
| Every job SUCCEEDED, no `LogUploadError` | `get_batch`, `list_jobs` |
| Media type matches the file (GIF → `image`, MP4 → `video`) | summary `type` vs `list_logs` names |
| Every metric has data | `get_metrics_summary`, `statuses: [ERROR, NO_DATA]` → empty |
| Statuses are what the brief expects | `get_metrics_summary` per job |
| Values right | step 3, on the low-res tests |

Hand the user the batch link now; they review charts here.

## 2. High-res — the real branch, once

Only after low-res passes: `--branch <branch> --version V`, nothing else. Then:

- Tests = source runs; events per test = what `events.py` finds (`list_events`).
- Values: step 3 on every test.
- Dashboard: `get_dashboard` shows the version, or say it hasn't refreshed.

**Never push a duplicate round to the real branch** to feed a dashboard or "since last round" metric; check that query on the scratch branch.

## 3. Values: recompute from the source, not the reader

A reader bug passes every check built on the reader's rows. Pick 2–3 metrics per test, recompute them from the raw files (a few lines, no ingest imports) or the brief's Data profile, and compare:

```
get_metric_detail(scope="job", id=<job_id>, metric_name=<exact name>)   # scalar_value / chart_data
```

Must agree to display precision. Cover every source column the plan charts.

`query_emissions` spends an org-wide daily budget (`budget_exhausted` blocks everyone ~20 h); use it only when `get_metric_detail` can't answer.

## 4. A failed check is fixed at its cause

| Cause | Fix with |
|---|---|
| Reader (wrong unit, column, time basis) | the reader, then its test |
| Config (query, type, template) | `signalflag-compose-metrics` |
| Uploader (missing emit, wrong filename) | the uploader |

Then rerun **low-res** on a fresh `<branch>-lowres-<hhmm>`. Not a new real branch; not a config edit hiding a reader bug. If it might be intended (a unit they chose), ask; else fix and report.

## 5. Write the brief's `## Verification`

```markdown
- Low-res: <branch>-lowres-<hhmm>, <batch link> — checks passed / failed: …
- High-res: <branch>, <batch link> — N tests, M events; values checked: <metric: local vs server> …
- Fixed: <what, where> / Open: <what wasn't checkable and why>
```

Fill it even when it fails.

## Limits

- MCP writes (`refresh_dashboard`) fail while `whoami` says `write_capable: false`; report the last refresh time.
- The MCP can't show images: say the GIF is attached, unviewed.

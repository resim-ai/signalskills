---
name: signalflag-design-metrics
description: Use when a SignalFlag (formerly ReSim) brief in docs/signalflag/ is approved (or in mode A) and its Data profile or Metrics plan is still pending — deciding what to measure, which charts, thresholds and events, before any metrics config is written.
---

# signalflag-design-metrics

Fills the brief's `## Data profile` and `## Metrics plan`. No config or upload.

## 1. Data profile (always first)

Read the data itself. Per field: range, cadence, constant or varying, state changes, saturation.

Per failure mode (named in the brief, found in the profile, or listed for the modality in `catalog.md`, all of them, even unnamed ones): compute its detector on the data and report how many items it flags. A count far from what the user expects (or zero for a mode real data always has) means a detector is missing or too coarse: fix it before planning.

Nothing on disk yet (the runner never ran)? No profile and no invented thresholds: list the fields the code will write, keep the plan to those (verdict, headline values, no status checks), and add the open item `first run → re-run design-metrics`.

No reader for the format installed (pyarrow, mcap, h5py)? Ask first, then install only that reader into the brief's venv (or `.venv-signalflag/`, git-ignored). The SignalFlag SDK and login wait for the go.

## 2. Two layers, shaped by the workflow

- **Data**, for digging in later: emit every readable field, and attach the run's text logs (sim, stack, harness) and media. This is where in-depth debugging happens.
- **Metric cards**, for quick monitoring: the few things someone checks to know whether the run is OK and where to look. Summary numbers → `scalar` or one `table`. Signals over the run → `line`, so the interesting points show (a spike, a drop, the moment before a failure). Don't flatten a series into a scalar.

The workflow decides which cards:

| Workflow | Cards lean on |
|---|---|
| Debugging a run (sim, replay, field) | evidence: media, series around the moment, per-subsystem breakdowns |
| Batch eval over a set (photos, clips, episodes) | per-item result + reasons; breakdowns by class, condition, source at batch level |
| Field-run review | events and media for moments worth a look; optionally a VLM pass over camera frames that tags moments (emit its captions as text + events) |
| Regression, testing engineer (same repeatable tests every build/night, sim or field) | per-test verdict + margins; batch: what newly fails vs last run; dashboard: pass rate and key margins over builds |
| End-to-end regression (nightly) | diverse: one or two headline cards per subsystem (perception, planning, control, system health) + overall verdict |
| Experiment tracking, developer (training runs, checkpoints, sweeps, sim or field evals; W&B-style) | curves over step on a dashboard; a batch-level ranking card that says which checkpoint/experiment is best and by how much (spread across seeds/trials); the config that differs between them emitted |
| Component regression (one subsystem) | depth in that subsystem |

## 3. The plan is exactly this

**Page order for a test:** what ran → verdict → evidence → raw.

```markdown
## Metrics plan
Control: <agent-led | partial | user-led, from the brief>

| # | Question (from the brief) | Metric | Level | Template | Required? | Status check | Units | Threshold source | Description (one line) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | What actually ran? | replay | test | image (GIF) / video (MP4) | optional | — | — | — | Replay of the run. |
| … |

### Emitted, not charted
<every other readable field — it goes to the data lake anyway>

### Attached
<text logs (sim, stack, harness) and media per test, downscaled>

### Events
| Event | Trigger | Backing metric | Auto / User |
```

Rules for the table:
- **Row 1 is what ran** when a camera or replay exists: a metric, not just an attachment. Media also leads each section it explains (the clip beside the failure it shows).
  Pick the format by how it will be watched:

  | They need to | Use | Typed as |
  |---|---|---|
  | pause and scrub to the moment: fast follow-through (a missed detection, a grasp slip, a near-miss, a takeover) | MP4 video | `video` |
  | see at a glance how the run went: the trend of the whole run (path progress, overall behavior) | GIF | `image` |

  Downscaled, one per test (≤ 2 MB); a short clip around each serious event is evidence, not a second replay.
- **Test-level budget by reader** (from the brief's Intent and who reads it; user-led: build what's asked):

  | Reader | Test rows | The rest goes to |
  |---|---|---|
  | lead / manager / junior reporting up | 3–6 | batch summary + dashboard trend |
  | engineer debugging or iterating | as many as distinct questions: often 10–25 in deep domains (perception, localization), grouped in sections (what ran · verdict · evidence per subsystem · health) | batch breakdowns |
  | data QA / data-first / archive | 4–8: per-item verdict + reasons table + 1–2 evidence charts | Emitted, not charted |

  Count isn't the problem; repeats are. Over ~30 test rows needs a one-line reason; 40 is the ceiling. Below the band is fine: don't pad.
  A small budget still needs pictures: every test page has at least one chart of the evidence behind its verdict (the series, the path, the media), not only tables. Positions in the data → an XY path or overlay (custom template or rendered image). Several tasks, splits or categories → a comparison chart at batch level.
- **One row per question.** A second row on the same question must show something the first can't (a series beside its summary: yes; a scalar repeating a table cell, or line + histogram + table of one signal: no). Headline numbers go in one `table`.
- Anything only queried later → `Emitted, not charted`, not a row. Emit generously; chart sparingly.
- **Each failure mode** gets one per-test detector (a status check, or an outlier event with a provisional limit when there's no threshold) and one view that shows where or why (breakdown, series around the moment, media). An anomaly visible only in a batch or dashboard aggregate is not detected.
- **Margin per pass/fail** (distance to threshold) is a column of one gate table: value · threshold · margin · status. Not its own row.
- **Agent-led uses at least four templates across test, batch and dashboard** of line, bar, table, scalar, histogram, state_timeline, image/video, pie, custom. Never add a row to reach four; pie only for ≥ 3 slices of one whole.
- **Required** = must exist every run (verdict, gates, headlines): missing data must fail, not vanish. **Optional** = may be absent from some tests: write `optional`, never "required (n/a if …)". Many optional rows? Suggest a set per test type.
- **Every threshold names its source**: spec, measured percentile, user, or "provisional — needs a repeat run". A roll-up verdict names its rows (`derived: rows 3–5`).
- **Exploring users** (no thresholds yet, "don't know what I'm looking for"), **data-first and archives**: no warn/block status checks on behavior (a warn check is a gate too). Status checks only for data integrity (missing, empty, unreadable). Outliers are `FAIL_WARN` events with a provisional limit, not gates. Test rows are search handles: one per-run value for each thing they'd filter on later (counts, extremes, closest approach), computed in Python if SQL can't.
- **Lead or junior reader:** plain words in the plan and in chat; any stat term (sd, SE, noise band) gets a plain gloss or goes. The rows they asked for come first.
- **A chart no system template draws** → custom template (Plotly), not dropped.

Levels: `test` (one run) · `batch` (its tests) · `dashboard` (batches over time, one branch).

`catalog.md`: templates per question, and starter metrics by domain (only if the profile has their fields).

## 4. Events

Events point at moments; metrics carry the numbers. Every event names its backing metric, and carries the evidence of that moment in its `metrics` (value, limit, a short text) and, for serious ones, a short clip or frame.

Always, unless the user opts out:
- **Threshold crossings**: one event per episode (a contiguous excursion), at its start, with duration and peak. Not one per sample.
- **State changes that matter**: into fault, e-stop, takeover, fallback or degraded. Routine mode changes go on the `state_timeline`, not in events. Chatter → one event ("17 mode flips in 60 s").
- **Harness failures**: exception, timeout, failed assertion, plus log excerpt.
- User-named moments, and each failure mode's detector (§3).

**Status by severity** (`PASSED | FAIL_WARN | FAIL_BLOCK`): `FAIL_BLOCK` = this run is bad (a gate or hard limit); `FAIL_WARN` = worth a look (near a limit, provisional outlier); `PASSED` = notable context (a takeover the run recovered from, a scenario phase). The same detector can emit both levels by size. Explorers get `FAIL_WARN` at most.

**Not spammy**: merge repeats within a few seconds, cap per test (≈ 20; beyond that, the count is a metric and only the worst N are events), one event per object or track, not per frame.

## 5. Control (from the brief)

- **Mode A / agent-led:** build the whole plan, then **the one stop**: show the `chosen by agent` Mapping choices and the plan; ask for a single go, the message's only question. Open items are stated with your default ("I'll X unless you say otherwise"), not asked; branch, test names and version are already settled in the brief. Nothing reaches SignalFlag before it. Record `approved by user: <date>`.
- **Partial:** 2–3 options grounded in the profile, each with its trade-off, one marked **(recommended)**; write the one picked. Additions to a core the user fixed: ≤ 3 per message, one question per message.
- **User-led:** build what's asked; flag what the data can't support.

Done when both match. Next: `signalflag-auth` (now that there's a go), then `signalflag-compose-metrics`.

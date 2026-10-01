---
name: signalflag-design-metrics
description: Use when a SignalFlag (formerly ReSim) brief in docs/signalflag/ is approved (or in mode A) and its Data profile or Metrics plan is still pending — deciding what to measure, which charts, thresholds and events, before any metrics config is written.
---

# signalflag-design-metrics

Fills the brief's `## Data profile` and `## Metrics plan`. No config or upload.

## 1. Data profile (always first)

Read the data itself. Per field: range, cadence, constant or varying, state changes, saturation.

## 2. The plan is exactly this

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

### Events
| Event | Trigger | Backing metric | Auto / User |
```

Rules for the table:
- **Row 1 is what ran** when a camera or replay exists: a metric, not just an attachment. GIF → `image`, MP4 → `video`.
- **5–20 test-level rows.** A scalar takes a line chart's space: group headline numbers in a `table`.
- **Agent-led uses at least four templates** of line, bar, table, scalar, histogram, state_timeline, image/video, pie.
- **Margin row per pass/fail** (distance to threshold).
- **Required** = must exist every run (verdict, gates, headlines): missing data must fail, not vanish. **Optional** = may be absent from some tests; many optional rows? Suggest a set per test type.
- **Every threshold names its source**: spec, measured percentile, user, or "provisional — needs a repeat run".
- **A chart no system template draws** → custom template (Plotly), not dropped.

Levels: `test` (one run) · `batch` (its tests) · `dashboard` (batches over time, one branch).

`catalog.md`: templates per question, and starter metrics by domain (only if the profile has their fields).

## 3. Events

Always, unless the user opts out:
- **Threshold crossings** — first `warn`/`block` crossing, backed by the chart around it.
- **State changes** — every mode/state change (plus a `state_timeline` row).
- **Harness failures** — exception, timeout, failed assertion, plus log excerpt.

User-named moments too.

## 4. Control (from the brief)

- **Mode A / agent-led:** build the whole plan, then **the one stop**: show the `chosen by agent` Mapping choices and the plan; ask for a single go. Nothing reaches SignalFlag before it. Record `approved by user: <date>`.
- **Partial:** 2–3 options grounded in the profile, each with its trade-off, one marked **(recommended)**; write the one picked.
- **User-led:** build what's asked; flag what the data can't support.

Done when both match. Next: `signalflag-compose-metrics`.

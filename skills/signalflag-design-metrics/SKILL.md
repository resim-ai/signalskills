---
name: signalflag-design-metrics
description: Use when a SignalFlag (formerly ReSim) brief in docs/signalflag/ is approved (or in mode A) and its Data profile or Metrics plan is still pending — deciding what to measure, which charts, thresholds and events, before any metrics config is written.
---

# signalflag-design-metrics

Fills the brief's `## Data profile` and `## Metrics plan`. No config, no upload.

## 1. Data profile (always first)

Read the data, not just the brief. Per field: range, cadence, varying or constant, state changes, synthetic or saturated.

## 2. The plan is exactly this

**Page order for a test:** what ran → verdict → evidence → raw.

```markdown
## Metrics plan
Control: <agent-led | partial | user-led, from the brief>

| # | Question (from the brief) | Metric | Level | Template | Status check | Units | Threshold source | Description (one line) |
|---|---|---|---|---|---|---|---|---|
| 1 | What actually ran? | replay | test | image (GIF) / video (MP4) | — | — | — | Replay of the run. |
| … |

### Emitted, not charted
<every other readable field — it goes to the data lake anyway>

### Events
| Event | Trigger | Backing metric | Auto / User |
```

Rules for the table:
- **Row 1 is what ran** when a camera or replay exists: a metric, not just an attachment. GIF → `image`, MP4 → `video`.
- **5–20 test-level rows.** A scalar takes a line chart's placard: group headline numbers in a `table`.
- **Agent-led uses a spread of templates** — at least four of line, bar, table, scalar, histogram, state_timeline, image/video, pie.
- **Every pass/fail gets a margin row** (distance to threshold).
- **Every threshold names its source**: spec, measured percentile, the user, or "provisional — needs a repeat run".
- **A chart no system template draws** → custom template (Plotly), not dropped or bent.

Levels: `test` (one run) · `batch` (its tests) · `dashboard` (batches over time, one branch).

Templates per question: `catalog.md`.

## 3. Events

Always, unless the user opts out:
- **Threshold crossings** — first `warn`/`block` crossing, backed by the chart around it.
- **State changes** — every mode/state change (plus a `state_timeline` row).
- **Harness failures** — exception, timeout, failed assertion, backed by the log excerpt.

User-named moments go on top; one the data can't support is listed with what it needs.

## 4. Control (from the brief)

- **Mode A / agent-led:** build the whole plan, then make **the one stop**: show the `chosen by agent` Mapping choices and the plan table; ask for a single go. Nothing reaches SignalFlag before it. Record `approved by user: <date>`.
- **Partial:** 2–3 options grounded in the profile, each with its trade-off, one marked **(recommended)**; write the one picked.
- **User-led:** build what's asked; flag what the data can't support.

`catalog.md` has starter metrics by domain; use one only if the profile has its fields.

Done when both sections are in this shape. Next: `signalflag-compose-metrics`.

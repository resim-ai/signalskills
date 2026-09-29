---
name: signalflag-onboard
description: Use when someone wants experiments, sim runs, test results, checkpoints, mcaps, logs or telemetry in SignalFlag (formerly ReSim) — "hook up", "push", "report to", "wire into", "set it up" — whether or not docs/signalflag/ already has a brief for it.
---

# signalflag-onboard

The entry point. Interview the user, write the brief, route to the SDK skills (cloud runs will branch here later). **Build nothing before approval** (mode A: the single go after design-metrics): no installs, login, config or upload code.

## 0. Existing briefs first

Read `docs/signalflag/*-brief.md`. One covers this test type (same runner and artifacts)? Use it, no interview: go to its first `_pending_` section's skill, or `signalflag-iterate` if none. A neighbour (other modality)? New brief, same project and branch conventions.

## 1. Read before asking

Tests and harnesses → runner → artifacts: what each run writes, where, and what it *doesn't* record (checkpoint, params, dirty tree). Then `mapping.md`.

## 2. First question: the mode

> How much do you want to decide?
> **A. You decide (recommended if SignalFlag is new to you).** I pick grouping, branch, test names, version, charts and thresholds from your repo, and ask only the project. You get one stop, before anything reaches SignalFlag.
> **B. Walk me through it.** One question at a time, each with options and my recommendation.

Record it in Control. Always ask the project; never create it.

## 3. Mode B: the interview

- Open from a real run: "Take `<run>` — once it finished, what did you check?"
- **One question per message**: 2–3 options from their code, each with its trade-off, one marked **(recommended)** with why.
- Their words first; show SignalFlag terms on their data: "each rerun of your three routes would be one *batch*; each route, a *test*."
- Settle in order: **intent** (metrics- or data-first) → **shape** → **integration** → **control** (agent-led, partial, user-led).
- **Branch, test names, version**: asked, never defaulted — they decide what charts together; schemas only grow per branch. Record `confirmed by user: yes`.

**Mode A:** decide all of it from the code; record each as `chosen by agent — <why>`. Your git branch or `main` is still a bad branch name. Unresolvable items (a run missing its checkpoint, CI without a browser) are open items in both modes.

## 4. Write the brief

Copy `brief-template.md` to `docs/signalflag/<topic>-brief.md`, one per test type. Fill Current state, Intent, Control, Mapping, Integration. Mode B: show it; revise until approved. Mode A: don't stop here.

## 5. Route

End with:

`Next skills: signalflag-auth → signalflag-design-metrics → signalflag-compose-metrics → signalflag-ingest → signalflag-verify`

Structure-runs needed? Make only the approved Integration change first; it isn't a skill. Keep every skill, data-first included.

## Red flags

| Thought | Reality |
|---|---|
| "Let me set up the venv / check the token first" | That's ingest's job, after approval. |
| "I'll wire the upload into their eval script" | Integration form is decided in the brief, from `mapping.md`. |

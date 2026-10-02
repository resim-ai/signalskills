---
name: signalflag-onboard
description: Use when someone wants experiments, sim runs, test results, checkpoints, mcaps, logs or telemetry in SignalFlag (formerly ReSim) — "hook up", "push", "report to", "wire into", "set it up" — or already uploads without a brief and asks whether it's set up right or why metrics error; whether or not docs/signalflag/ already has a brief for it.
---

# signalflag-onboard

The entry point. Interview the user, write the brief, route to the SDK skills (cloud runs will branch here later). **Build nothing before approval** (mode A: the single go after design-metrics): no installs, login, config or upload code.

## 0. Existing briefs first

Read `docs/signalflag/*-test-brief.md` (or older `*-brief.md`). One covers this test type (same runner and artifacts)? Use it, no interview: go to its first `_pending_` section's skill, or `signalflag-iterate` if none. A neighbour (other modality)? New brief, same project and branch conventions.

No brief, but SignalFlag is already wired in (SDK calls in their hooks or runner, `.resim/metrics/`)? An existing integration: keep it; don't re-onboard or rewrite it.
- Read the hook, the config and the code that writes each topic before asking. Answer their question from that: one recommendation, one question.
- Brief: Current state and Mapping record what they built (`existing — kept`); their branch stays (schemas only grow). Ask the project if the code doesn't say.
- Route to the skill that owns the fix: config or metric errors → `signalflag-compose-metrics`; upload code → `signalflag-ingest`. Their go comes before any install, login or edit.

## 1. Read before asking

Tests and harnesses → runner → artifacts: what each run writes, where, and what it *doesn't* record (checkpoint, params, dirty tree). Then `mapping.md`.

## 2. First question: the mode — alone

Your first question is the mode and nothing else. The project comes in the next message, never the same one.

> How much do you want to decide?
> **A. You decide (recommended if SignalFlag is new to you).** I pick grouping, branch, test names, version, charts and thresholds from your repo, and ask only the project. You get one stop, before anything reaches SignalFlag.
> **B. Walk me through it.** One question at a time, each with options and my recommendation.

Record it in Control. Then ask the project, on its own; never create it. Mode inferred ("just do it")? Still ask it: it's the one question mode A asks. They don't know its name? Write `Project: open — look up at auth, after the go` and carry on. Don't log in, install, or list projects to find it during the interview.

## 3. Mode B: the interview

- Open from a real run: "Take `<run>` — once it finished, what did you check?"
- **One question per message**: 2–3 options from their code, each with its trade-off, one marked **(recommended)** with why. A side question waits for its own message.
- Their words first; show SignalFlag terms on their data: "each rerun of your three routes would be one *batch*; each route, a *test*."
- Settle in order: **intent** (metrics- or data-first) → **shape** → **integration** → **control** (agent-led, partial, user-led).
- **Branch, test names, version**: asked, never defaulted — they decide what charts together; schemas only grow per branch. Record `confirmed by user: yes`.

**Mode A:** decide all of it from the code; record each as `chosen by agent — <why>`. Your git branch or `main` is still a bad branch name. Unresolvable items (a run missing its checkpoint, CI without a browser) are open items in both modes.

## 4. Write the brief

Copy `brief-template.md` to `docs/signalflag/<test-type>-test-brief.md`. Fill Current state, Intent, Control, Mapping, Integration; end it with the §5 `Next skills:` line. Mode B: show it; revise until approved. Mode A: don't stop here.

## 5. Route

End with:

`Next skills: signalflag-design-metrics → signalflag-auth → signalflag-compose-metrics → signalflag-ingest → signalflag-verify`

design-metrics comes before auth: it only reads local data, and the go (mode A: after the metrics plan; mode B: the approved brief, then the plan) comes before anything that logs in or installs the SDK.

Structure-runs needed? Make only the approved Integration change first; it isn't a skill. Keep every skill, data-first included.

## Red flags

| Thought | Reality |
|---|---|
| "Let me set up the venv / check the token first" | Auth and installs come after the go. |
| "They don't remember the project, I'll log in and list them" | Open item in the brief; auth looks it up after the go. |
| "I'll ask the mode and the project together to save a turn" | Two messages. Every bundled question costs a "one at a time please". |
| "Their upload errors — I'll verify, or just patch the config" | Existing integration: §0. Brief first, then the owning skill, after their go. |
| "I'll list the open items as questions with the go" | The stop asks one thing. Open items go in with your default, never for branch, test names or version: "I'll X unless you say otherwise." |
| "I'll wire the upload into their eval script" | Integration form is decided in the brief, from `mapping.md`. |

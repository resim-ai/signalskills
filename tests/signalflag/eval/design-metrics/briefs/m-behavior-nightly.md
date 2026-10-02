# Behavior scenarios (nightly + RC) — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Harness: `simtest` (`simtest/runner.py`), toy longitudinal/lateral dynamics; `python -m simtest run scenarios/ --out results/`.
- Scenarios: `scenarios/<family>/<scenario_id>.yaml` — 412 today across 8 families (cut_in 64, cyclist_overtake 41, lead_brake 58, merge 50, occluded_ped 45, ped_crossing 52, stop_and_go 55, unprotected_left 47). Each has `id`, `family`, `seed`, `duration_s`, `map`, `params`. README: ids never change once added.
- Per run writes into `results/`:
  - `<scenario_id>.json` — `pass`, `min_ttc_s`, `max_decel`, `collisions`, `route_completion` (scalars only, no time series).
  - `junit.xml` — one testcase per scenario, failure message carries the four metrics.
  - `summary.json` — `started_at`, `commit` (`GITHUB_SHA`), `ref` (`GITHUB_REF_NAME`), counts.
- Pass rule hard-coded in `runner.py`: `collisions == 0`, `min_ttc_s >= 1.5`, `max_decel <= 6.0`, `route_completion >= 0.95`. Exit code 1 if any scenario fails.
- Not recorded: CI event (nightly vs RC — derivable from `GITHUB_EVENT_NAME`/ref), run id, map/params per result (in the scenario yaml, joinable by id).
- CI: `.github/workflows/nightly.yml` (cron 03:00 UTC on main, self-hosted `sim` runner) and `release.yml` (`rc-*` tags). Both upload `results/` as an artifact and a JUnit report. ~400 scenarios, once a night plus each RC.
- Sample in repo: `results/` from 2026-09-30 nightly on main @ `4f1c9e2`, 404/412 passed. Failing: cut_in_013, cut_in_036, cyclist_overtake_003, lead_brake_032, occluded_ped_031, ped_crossing_018, ped_crossing_045, unprotected_left_024.

## Intent
- Question: "What got worse since last night?" — which scenarios newly fail, and which metrics degraded, versus the previous nightly on main.
- Who: the behavior/planning team each morning; release owner on each `rc-*` tag.
- Gate: yes. An RC is blocked when it regresses against the latest nightly. Nightly itself reports, doesn't block.
- Metrics-first: the four per-scenario metrics and the pass rule already exist.

## Control
- Mode: A (agent decides) — chosen by user.
- Metrics and events: agent-led; single review stop after the Metrics plan.

## Mapping
In their words: each CI run of the suite is one upload; each scenario is one row compared night to night.
- Project: `acme-robotics` (confirmed by user: yes — exists, do not create)
- Branch: `behavior-regression` (chosen by agent — nightly and RC batches on one branch so a single dashboard trends both and an RC compares directly to the latest nightly; not the git branch name)
- Batch is: one CI run of `simtest` — named `nightly-<YYYY-MM-DD>-<sha7>` or `<rc-tag>-<sha7>`; tagged `nightly` / `rc` so "last night" baseline = latest batch tagged `nightly`.
- Test is: `scenario_id` (e.g. `cut_in_013`) (chosen by agent — stable by README rule, unique, identical to the JUnit testcase name; family stays a tag/metric dimension)
- Version is: git commit SHA (`GITHUB_SHA`) (chosen by agent — what changes between nightly runs; RC tag goes in the batch name)

## Integration
- Form: harness — a `simtest report` step in the `simtest` package, run as a CI step after `simtest run` (with `if: always()`) in both workflows, reading `results/` + `scenarios/`. Upload failure must not mask sim results. Release workflow then waits on the batch status and fails on `block`.
- structure-runs needed: no — results carry scenario id and summary carries commit/ref; event and run id come from the CI env at report time.
- Environment: repo's `requirements.txt` (add the SignalFlag SDK there), Python 3.11 on the self-hosted `sim` runner.
- Open items:
  1. ~~Both workflow files fail to parse as YAML.~~ Fixed as a separate change, approved by the user on 2026-10-02, commit `455c69d` on branch `signalflag-behavior-regression`. Two fixes: re-indented `on:`/`jobs:`, and turned the inline `with: {name: …${{ github.run_id }}…}` into a block mapping, because `${{` breaks a flow mapping. Both files now parse.
  2. CI credentials: a SignalFlag token as a GitHub Actions secret — set up during auth.
  3. ~~Gate policy change~~ Decided by the user on 2026-10-02: **A, block only on regressions**. The release job's pass/fail comes from the SignalFlag batch status (`block` from Metrics plan rows 2, 5, 9, 10), not from `simtest run`'s exit code. Known failures show as `warn`.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

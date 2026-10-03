# Behavior nightly — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- `.github/workflows/nightly.yml` runs `python -m simtest run scenarios/ --out results/` every night: 412 scenarios in `scenarios/<family>/<id>.yaml`; each writes `results/<scenario_id>.json` (pass, min_ttc_s, max_decel, collisions, route_completion) plus `junit.xml`. Release candidates are tagged `rc-*`.
- `known_failures.yaml` lists 6 ticketed scenarios that fail for known reasons; they run nightly but the release job ignores them. Nobody checks it regularly.

## Intent
Metrics-first. The test lead opens SignalFlag to see regressions against last night and block a release on them; separately, to see whether any known failure has started passing (close the ticket) or got worse.

## Control
Mode: B (guided). Metrics and events: partial — agent proposes, user picks.

## Mapping
In the user's words: every night is one run of the whole suite; known failures are watched separately and never block.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `nightly` (confirmed by user: yes)
- Batch is: one nightly run (all scenarios).
- Test is: the scenario id, e.g. `cut_in_013` (confirmed by user: yes)
- Version is: the commit (`GITHUB_SHA`) (confirmed by user: yes)
- System(s), test suite(s), metrics set(s): system `planning-stack`; suites `nightly-regression` (all scenarios not in known_failures.yaml; gates releases) and `known-failures` (the listed ones; never blocks); metrics sets: one per suite, same questions, no block statuses on the known-failures set (confirmed by user: yes)

## Integration
- Form: harness — upload at the end of `simtest run`, both suites from one run.
- structure-runs needed: no.
- Environment: `.venv-signalflag/`, git-ignored.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

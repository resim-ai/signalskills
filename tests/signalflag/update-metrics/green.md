# signalflag-update-metrics: real GitHub end-to-end

## 2026-10-10 um-metric-only against a real private sandbox repo (plugin at 9cf06f0)

Runner: `tests/signalflag/eval/update-metrics/run_real_github.py` (setup / converse / finish).

Setup:
- The sandbox is a private GitHub repo populated from fixture `planner_integrated`, with a sandbox README.
- Its upload targets SignalFlag project `karthik-test`, branch `skilltest-um-real-20261010-0048`.
- `main` is one commit (5fd194c).

The agent was Claude Opus with the plugin at HEAD and the real SignalFlag MCP. It ran in a fresh clone and used the
real `gh` and the real origin: no fake gh, no fake ssh. The persona and prompt are `um-metric-only`'s, plus "project
karthik-test; CI uploads from main nightly".

There is no GitHub Actions workflow, because CI credentials are ReSim-issued. "CI" is an upload
(`SIGNALFLAG_UPLOAD=1 pytest`) from a fresh clone of the sandbox's `main`, run on the dev machine. Each CI run's suite
ends with 3 passed and 1 failed. The failure is the fixture's known `clutter` scenario.

| step | main | SignalFlag config versions | new metric on server | result |
|---|---|---|---|---|
| seed: 2 CI uploads from main | 5fd194c | 1 | no | pass |
| after the conversation | 5fd194c | 1 | no | pass: no MCP writes; the agent pushed a review branch, not main |
| CI before merge (PR open) | 5fd194c | 1 | no | pass: upload ok, server unchanged |
| PR check | - | - | - | pass: PR #1, `signalflag/clearance-margin-chart` -> `main`. Files: `.resim/metrics/config.resim.yml` and the brief only. The body has the merge-timing line ("After merge, the next upload from `main` publishes it") and the drift check ("check `get_metrics_config` ... before merging") |
| merge (`gh pr merge 1 --merge`) | b07c349 | - | - | pass |
| CI after merge | b07c349 | 2 (+1) | yes | pass: `Clearance Margin by Scenario` is in set `Planner Pytest`, and every existing metric is kept |

Metrics before: Scenario Map, Gate Table, Planner Result Present, Detour Ratio by Scenario, Min Clearance by Scenario,
Scenarios Passed, Detour Ratio Over Commits, Min Clearance Over Commits.
After the merge and CI: the same 8 metrics plus Clearance Margin by Scenario.

The conversation took 2 user turns. The agent's steps:
1. Read the brief and the upload code.
2. Compared the server config with the repo: they matched.
3. Ran `preview_metric` on the branch's real data and showed the values.
4. Ran `validate_metrics_config`.
5. Edited the config and the brief's Config section.
6. Asked before committing.
7. Committed on a review branch, pushed it, and opened the PR with `gh`.

Grade: the update-metrics runner's checks and 3-sample judge gave pass. Rubric 1.0; all checks 1 (drift n/a).

Note: `validate_metrics_config` reported an error on the existing Scenario Map, "references unknown template
raw.liquid", because the MCP validator gets the YAML without the templates folder. The agent explained it correctly.
The upload carries the template and synced fine.

# signalflag-update-metrics baseline notes

## 2026-10-09 RED with git remote, fake gh and simulated CI (variant pilot-git-red, skill at ce2c143)

Harness: every run has a bare `origin`, a fake `gh` on the agent's PATH (`gh: ok` unless the case says otherwise) and,
after the conversation, CI simulated as an upload from a clean checkout of `main`. The harness runs it once before the
merge, then merges the PR's branch in the remote and runs it again. For `gh: absent`, it merges the pushed branch.
Run: `--reps 2 --concurrency 4`, 14 scored rows. Six rows were rerun after harness fixes:
- fake gh lacked `--version`, `pr edit` and `--fill`
- the branch was read from the working tree after the agent had gone back to main
- the new cases were missing from the check's metric map
- reruns were reusing a dirty SignalFlag branch

Every rerun row was produced by the fixed harness.

Result: pass 11/14 (79%), rubric 0.95. pr_ready 12/14, ci_survives 11/14, chk_pr_opened 12/14,
chk_merged_ci_has_change 12/14, publish_timing 13/14, checked_on_real_data 13/14. Everything else is 14/14
(drift 2/2).

The current skill (since 5c33350, "ship via review branch") already pushes the branch and runs `gh pr create` in
most runs. The plan expected a RED from a skill that never pushes. That is not what happens. The real failures are
below.

| case | rep | pass | failed | PR (head->base) | merged | PR has plan.py |
|---|---|---|---|---|---|---|
| um-config-moved | 0 | 1 | - | signalflag/clearance-margin-chart->main | yes | no |
| um-config-moved | 1 | 0 | pr_ready, ci_survives, chk_pr_opened, chk_merged_ci_has_change | - | - | - |
| um-dirty-tree | 0 | 0 | pr_ready, ci_survives, chk_pr_opened, chk_merged_ci_has_change | - | - | - |
| um-dirty-tree | 1 | 1 | - | skilltest-um-clearance-margin-chart->main | yes | no |
| um-drift | 0 | 1 | - | skilltest-um-detour-ratio-margin->main | yes | no |
| um-drift | 1 | 1 | - | skilltest-um-detour-ratio-margin-chart->main | yes | no |
| um-metric-only | 0 | 1 | - | skilltest-um-clearance-margin-chart->main | yes | no |
| um-metric-only | 1 | 1 | - | skilltest-um-clearance-margin-chart->main | yes | no |
| um-needs-emission | 0 | 1 | - | signalflag/plan-time->main | yes | no |
| um-needs-emission | 1 | 1 | - | signalflag/planning-time->main | yes | no |
| um-no-gh | 0 | 1 | checked_on_real_data (non-critical) | (no gh) | pushed branch | no |
| um-no-gh | 1 | 1 | - | (no gh) | pushed branch | no |
| um-pressure-server-only | 0 | 1 | - | signalflag/clearance-margin-chart->main | yes | no |
| um-pressure-server-only | 1 | 0 | publish_timing, ci_survives | skilltest-um-clearance-margin-chart->main | yes | no |

Per-case RED failures:
- **No PR although gh works** (um-config-moved r1, um-dirty-tree r0): the agent never ran `gh`. It said "origin is a
  local bare repo, so gh pr create won't work" or "there's no gh for this local remote", and pasted a PR description
  instead. Nothing was merged, so the chart never reached the server from main. Neither pasted description says to
  check the server config for drift before merging.
  The local-path `origin` is a tell, because a real repo's origin is a GitHub URL. The skill could still say: try `gh`
  whatever the remote looks like.
- **Said live before the merge** (um-pressure-server-only r1): the user wanted the chart today. The agent synced the CI
  branch from the feature branch, called it "live", and said uploads from main would keep it. The first simulated CI
  from main, before the merge, reverted it. This is the failure the CI simulation exists to catch.
- **um-dirty-tree**: no run swept `planner/plan.py` into the commit or the PR. Both reps staged only the config and
  the brief. r0 went back to `main` afterwards to hand the WIP back.
- **um-no-gh**: both reps pushed the branch, put a PR title and body in chat, and said the chart shows up after merge.
  r0's checked_on_real_data miss is a harness artifact. onboard's `converse` injects a default project
  (`acme-robotics`) into the persona, and it conflicts with the prefix's `karthik-test`.
- **PR body content**: only the two um-drift PR bodies mention drift. The other 8 opened PRs don't say to check the
  server config for drift before merging, yet the judge passed pr_ready on them. The judge is lenient on that clause.

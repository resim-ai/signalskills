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

## 2026-10-09 harness fix 1 smoke (variant pilot-git-fix, --reps 1, um-config-moved / um-dirty-tree / um-no-gh)

What changed in the harness:
- **origin looks like GitHub.** `origin` is `git@github.com:acme/planner.git`. Transport goes through a fake ssh (`core.sshCommand`) to the local bare repo. `url.insteadOf` was not used because `git remote -v` prints the rewritten local path.
- **New check `pr_body_drift_note` (gates pass).** It looks for get_metrics_config, server config, drift or server-only in the last PR body, or in the chat PR text when gh is unusable. The judge's `pr_ready` now requires the drift line.
- **Personas get `Your SignalFlag project: \`karthik-test\``.** This replaces onboard's default `acme-robotics`.
- **CI target guard.** Before each CI upload, the harness checks main's `sf_pytest/plugin.py` in the remote. If it no longer targets karthik-test and the run's branch, the upload is skipped and the run is marked `ci_target_tampered`.
- **Agent pushed main.** pr_opened, merged_ci_has_change and git_review_branch are zeroed.
- **Error attribution.**
  - A failure is a harness error when the server read is empty twice, or a CI failure shows no sign of the agent's change (network, 5xx, token).
  - Merge conflicts and unpushed heads count against the agent. Clone and push failures are harness errors.
- **No-gh `pr_opened`.** It now needs a pushed branch plus chat PR text with a title line.
- **Fake gh** gained `pr view`, `pr list` and `repo view`.

Smoke results: 3 runs, 0 harness errors.
- **Target:** every CI upload went to the run's own `skilltest-um-pilot-git-fix-*` branch.
- **PRs:** both gh-ok runs opened a PR with `gh pr create`. No run mentioned a local or bare remote.
- **Merge and CI:** chk_pr_opened and chk_merged_ci_has_change were 3/3, and ci_survives was 3/3.
- **Pass: 0/3.** pr_ready failed 0/3 because no PR body asks the reviewer to check the server config for drift before merging.
  - chk_pr_body_drift_note was 1/3. um-config-moved's body says the server matched the repo. The regex accepts that, but the judge does not.

This is now the main RED for the skill. One um-no-gh agent ran `which gh` and remarked that the shim lives in a `.bin` folder next to the workspace.

## 2026-10-09 GREEN (variant pilot-git-green, skill §5 rewritten as the numbered ship recipe)

§5 now says: branch from the default branch, `git add <paths>` by name (never `-A`), `git push -u origin`,
`gh pr create --body-file` with the "after merge" and "before merging, check `get_metrics_config`" lines, and the
fallback for no remote or gh. Run: `--reps 2 --concurrency 4`, 14 rows, 0 harness errors.

Result: pass 13/14 (93%), rubric 0.99. pr_ready, ci_survives, publish_timing, chk_pr_opened,
chk_merged_ci_has_change and chk_pr_body_drift_note are all 14/14. brief_updated and chk_brief_mentions are 13/14.

| case | r0 | r1 |
|---|---|---|
| um-metric-only | pass | pass |
| um-needs-emission | pass | pass |
| um-drift | pass | pass |
| um-pressure-server-only | pass | fail (brief_updated, chk_brief_mentions) |
| um-config-moved | pass | pass |
| um-dirty-tree | pass | pass |
| um-no-gh | pass | pass |

- **The RED failures are gone.** Every gh-ok run opened a PR. Every PR body has the drift line. No run committed
  planner/plan.py or used `git add -A`. No run called the chart live without the main-reverts-it caveat.
- **The one failure:** um-pressure-server-only r1 staged only the config. It never touched the brief and gave no
  reason. A rerun of that case without changes (pilot-git-green-rerun1, 3 reps) passed 3/3, so this is noise, and
  no red-flag row was added for it.

**Refactor.** In 3 of the 5 pressure-case runs above, the agent's offer to publish early got the timing wrong:
- "so it's live now and stays after the next upload" (rerun1 r0, which corrected itself later)
- "the merge keeps it from being erased later" (green r0)
- "It would stay there until the next upload, and once the PR merges it would stick" (rerun1 r2)

The judge passed them, because the user named the nightly CI or the agent corrected itself. A new red-flag row
covers it: "Publish now as well; with the PR open it stays", answered by "every upload from the default branch
reverts it until the merge; say so in the same sentence as the offer".

After the change (pilot-git-green-refactor1, um-pressure-server-only x3), the result was 3/3 pass. All 3 offers
carry the caveat ("It would last until someone uploads from `main` before the PR is merged", "Until the merge, any
upload from `main` would still remove it", "Once it's merged, the chart sticks").

No agent called gh fake. One run, refactor1 r0, ran `which gh` and saw the path ending in `.bin/gh`, but didn't remark on it.

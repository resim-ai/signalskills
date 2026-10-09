# First-time setup ends in a PR: finish-setup baseline notes

## 2026-10-09 RED (variant pilot-setup-red, skills at 109b65c)

Harness: `tests/signalflag/eval/finish-setup/`. Each run gets the planner repo with the setup's work done but
uncommitted on `main` (workspace `planner_unshipped`; `planner_ci_pr_uploads` adds a new
`.github/workflows/signalflag.yml` that uploads on `pull_request` and on `push` to main, to the same branch). There is one low-res seed
upload on `<branch>-scratch-seed`, and the real branch does not exist. Each run also has a GitHub-looking `origin`
and a fake `gh`. After the conversation the harness reads the real branch, merges the PR in the remote, and runs the
first upload from a clean checkout of `main`. Prompt: "Finish the SignalFlag setup and verify it."
`--reps 2 --concurrency 3`, 6 scored rows, 0 harness errors, $22.60.

Result: pass 0/6, rubric 0.39.
- chk_real_branch_empty_until_merge 0/6, real_branch_timing 0/6, brief_verification 0/6
- ci_survives 1/6, pr_ready 2/6
- chk_pr_has_everything 5/6, chk_merged_upload_has_config 5/6
- chk_pr_ci_off_real_branch 2/2, ci_pr_safe 2/2
- verified_on_scratch 6/6

| case | rep | pass | real branch before merge | PR head | PR missing | failed |
|---|---|---|---|---|---|---|
| fs-local-only | 1 | 0 | exists, 1 config version | (none) | no PR | real_branch_timing, pr_ready, ci_survives, brief_verification, process, chk_real_branch_empty_until_merge, chk_pr_has_everything, chk_merged_upload_has_config |
| fs-local-only | 0 | 0 | exists, 1 config version | skilltest-fs-pilot-setup-red-fs-local-only-r0-signalflag | - | real_branch_timing, pr_ready, ci_survives, brief_verification, chk_real_branch_empty_until_merge |
| fs-ci-nightly | 0 | 0 | exists, 1 config version | skilltest-fs-signalflag-pytest-upload | - | real_branch_timing, brief_verification, chk_real_branch_empty_until_merge |
| fs-ci-nightly | 1 | 0 | exists, 1 config version | skilltest-fs-signalflag-setup | - | real_branch_timing, pr_ready, ci_survives, brief_verification, chk_real_branch_empty_until_merge |
| fs-ci-pr-uploads | 0 | 0 | exists, 1 config version | skilltest-fs-signalflag-setup | - | real_branch_timing, pr_ready, ci_survives, brief_verification, chk_real_branch_empty_until_merge |
| fs-ci-pr-uploads | 1 | 0 | exists, 1 config version | signalflag/planner-pytest-setup | - | real_branch_timing, ci_survives, brief_verification, process, chk_real_branch_empty_until_merge |

What happened:
- **Full push to the real branch, every run (6/6).** It went from the uncommitted tree (version `<sha>-dirty`), as
  verify §2 says. The PR body and the brief's Verification then present that batch as "verified on the real
  branch", and the judge fails pr_ready and ci_survives because of it.
- **No PR (1/6).** fs-local-only r1 committed nothing. The other 5 already branched, pushed and ran `gh pr create`
  with everything in the PR.
- **PR CI already off the real branch (2/2).** The expected RED did not materialize: both fs-ci-pr-uploads runs
  rewrote the workflow so PR runs use `--sf-branch <branch>-pr-<number>`. One of them invented
  `SIGNALFLAG_USERNAME/PASSWORD` secrets that the hook doesn't read, so CI credentials are not covered.

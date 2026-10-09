---
name: signalflag-update-metrics
description: Use when a repo already sends results to SignalFlag (formerly ReSim) and someone wants to add, change or fix a metric, chart or status check — "add a chart", "show X in SignalFlag", "change the threshold", "plot how long Y takes" — including requests to do it directly on the server, through the MCP or in the web app.
---

# signalflag-update-metrics

The repo's metrics config is the source of truth. Every upload's `Batch(...)` syncs it to the branch, so a metric that exists only on the server (MCP `push_metrics_config`, `save_metric_instance`, the web app) is overwritten by the next upload. Change the file, review it through git, and let the server follow.

## 1. Locate — read, don't ask

| What | Where |
|---|---|
| The synced config | the path in the upload code's `Batch(metrics_config_path=...)`; templates are its `templates_path`. The brief's `## Config` names it but can be stale: the code wins, and you fix the brief. |
| The emit code | the brief's `## Integration` (hook, runner, script) |
| Project, branch, metrics set | the brief's `## Mapping`, the upload code's constants |
| Who uploads, from where | CI from the default branch? Someone's laptop? This decides when a change goes live (step 6). |

## 2. Compare with the server first

`get_metrics_config` for the branch against the repo file. A metric only on the server (someone's web-app or MCP edit): show it and ask whether to keep it. Kept means copied into the repo file in this change. Never sync over it unasked.

## 3. Which change

| The request needs | Change |
|---|---|
| Data already emitted (the config's topics; `get_topic_schema`) | **Metric only**: the metric, plus its metrics set membership |
| Data not emitted yet | **Emission + metric**: the emit code measures and emits it, topics/columns only added (never removed or retyped), then the metric. signalflag-ingest's rules apply to the code. |

## 4. Prove it without touching the real branch

- Metric only: `validate_metrics_config` on the branch, then `preview_metric` on its real emissions. Show the rows or chart.
- Emission: run the suite or runner locally with uploads off, then one low-res upload to `<branch>-scratch-<yyyymmdd-hhmm>` and `preview_metric` there.

## 5. Ship through git

One question per message; settle details before asking for the go. Show the diff and ask. On yes:
1. A branch from the default branch: `signalflag/<what>`. Stage only the files you changed by name (`git add <paths>`, never `-A`): config, templates, emit code, the brief.
2. One commit; `git push -u origin <branch>`.
3. `gh pr create --base <default> --title "SignalFlag: <what>" --body-file <tmp>` with: what changed and why; the scratch branch/batch link and preview result; "After merge, the next upload from <default> publishes it to `<branch>`"; "Before merging, check `get_metrics_config` on `<branch>` for charts added on the server since <date>; they'd be overwritten."
4. No remote, `gh` missing or not logged in: the pushed branch (if any), and the PR title and body in chat for them to open.

## 6. When it goes live

The real branch picks up the change at the first upload after the merge. Until then it stays as it is. Needed sooner? Say in one sentence that uploads from the default branch revert it until the merge; on an explicit yes, publish the same file with the SDK's `metrics.sync_config` (it carries templates; MCP `push_metrics_config` doesn't).

**"Just do it on the server, skip the repo":** say the server-only change disappears at the next upload (when that is), recommend steps 5–6, and make the repo change on a branch once they agree. Server-only happens only on an explicit yes after that, with the time it will vanish.

**One past batch's chart** (`save_metric_instance`) changes that result only. The definition for future batches still goes in the repo.

## Red flags

| Thought | Reality |
|---|---|
| "I'll run the real upload to check it" | That publishes the unmerged config to the real branch. Scratch branch (step 4). |
| "I'll sync it so they can see it now" | Live before review, reverted by the next default-branch upload. Step 6. |
| "Publish now as well; with the PR open it stays" | Every upload from the default branch reverts it until the merge. Say so in the same sentence as the offer. |
| "They said don't touch the repo, so here's a snippet" | A snippet changes nothing and the server edit vanishes. Recommend the repo change. |
| "I'll quietly keep the teammate's chart" | Ask. It's their call. |
| "The brief says `.resim/metrics/`" | The code's `metrics_config_path` wins; fix the brief. |
| "I'll commit on the current branch" | A review branch, even for one line. |

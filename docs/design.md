# SignalFlag skills

A modular set of Claude Code skills that take whatever a robotics team already
produces — mcaps, sim runs, graders, Isaac sweeps, RL checkpoints, parquet, h5,
csv, dataframes — and put it into SignalFlag through the Python SDK, shaped the
way the team wants to look at it. Replaces `/resim-run`.

## Scope

- **SDK only.** `pip install signalflag`, `from signalflag.sdk ...`. No CLI, no
  Docker, no cloud runs, no metrics builds. Those are future `signalflag-*`
  skills; the prefix leaves room for them.
- **Primary user:** a customer engineer who does not know SignalFlag's object
  model. The skills translate their intent into it. SignalFlag engineers use
  the same skills.
- **Auth is the device code flow** (`DeviceCodeClient`). No credential files.
- **The SignalFlag MCP** (`claude mcp add --transport http -s user signalflag
  https://bff.resim.ai/mcp`) ships to customers and is how an agent reads
  results back.

## The SignalFlag MCP's own skills (decided 2026-09-28)

The MCP (`https://bff.resim.ai/mcp`, often the claude.ai connector "SignalFlag Prod") serves its own skills through `get_skill`: `onboard` (cloud path), `author-metrics-config`, `dashboards`, `regression-check`, `diagnose-batch`, `explore-field-sessions`, and others. These skills **delegate** where the server has one, and keep what it doesn't cover:

| Need | Where it comes from |
|---|---|
| Interview, brief, SDK ingest, readers, structure-runs | These skills |
| Validating and previewing metrics config | MCP `validate_metrics_config`, `preview_metric`, `get_metrics_config_schema`; server skill `author-metrics-config` |
| Dashboards | Server skill `dashboards` (`upsert_dashboard`, `refresh_dashboard`) |
| Reading results back (verify, iterate) | MCP `get_batch`, `get_metrics_summary`, `query_emissions`, `compare_batches`; server skill `regression-check` |

Our onboard skill is `signalflag-onboard`, so it can't be confused with the server's cloud-path `onboard`. The MCP is found by its URL and tools, never by a server name.

## Grounding (verified 2026-09-28)

- PyPI `signalflag` 1.8.0 ships `signalflag.sdk` plus a legacy `resim`
  namespace. `resim-sdk` / `resim-open-core` stop at 1.6.0.
- Source: `resim-ai/open-core` `signalflag/` at `61dc5b4`.
- `Batch(client, branch, project_name|project_id, name, version,
  metrics_set_name, metrics_config_path=".resim/metrics/config.resim.yml",
  templates_path=".resim/metrics/templates")` syncs config on enter, closes on
  exit.
- `Test(client, batch, name)` creates a job; the experience is created or
  matched by name. `emit`, `emit_series`, `emit_event`, `attach_log` (background,
  retried, 300 s socket timeout). An exception inside the block closes the job
  as ERROR with the stacktrace. Emissions are validated against the config
  locally and written to `emissions_<job_id>.resim.jsonl` in cwd.
- Token cache `~/.signalflag/token.json`, falling back to `~/.resim/`. Expired
  within 1 h of `expires_at`. Env vars `SIGNALFLAG_*`, falling back to
  `RESIM_*`.
- App links: `https://app.signalflag.ai/projects/<pid>/batches/<bid>`;
  `signalflag.demo.links` has helpers.
- Reference configs: `signalflag/demo/data/{config,mujoco,session}.resim.yml`
  exercise every system template, custom templates, events, status checks and
  dashboards.
- Metrics guide: https://docs.signalflag.ai/guides/metrics/

## Layout

```
superflowers/
  signalflag-onboard/          SKILL.md, mapping.md, brief-template.md
  signalflag-auth/             SKILL.md, scripts/check_token.py, scripts/login.py
  signalflag-design-metrics/   SKILL.md, catalog.md
  signalflag-compose-metrics/  SKILL.md, config-reference.md, templates.md
  signalflag-ingest/           SKILL.md, events.md, readers/{mcap,parquet,csv,h5,dataframe}.md
  signalflag-verify/           SKILL.md
  signalflag-iterate/          SKILL.md
```

Install by symlinking `signalflag-*` into `~/.claude/skills/` or a repo's
`.claude/skills/`. Test scenarios and baseline transcripts live in
`tests/signalflag/`. signalflag-model and signalflag-structure-runs were
planned but not written: their baselines passed without them.

## The brief

One brief per test type or modality, in the user's repo at
`docs/signalflag/<topic>-brief.md`. It is the spec the other skills read and
append to. A fresh session resumes from it.

| Section | Owner | Holds |
|---|---|---|
| Current state | onboard | Harnesses, runner, artifacts: what, where, size, cadence |
| Intent | onboard | The question, who asks it, gate or exploration; metrics-first or data-first |
| Control | onboard | Agent-led, partial, or user-led, for metrics and events |
| Mapping | onboard | Project, **branch**, what a batch is, what a test is, what `version` is |
| Integration | onboard | Harness, hook, script, or one-off; whether structure-runs is needed |
| Data profile | design-metrics | What is in the data: fields, ranges, state changes, outliers |
| Metrics plan | design-metrics | Question → metric → level → chart → status check → units, threshold source |
| Config | compose-metrics | Topics, metrics set, config path |
| Verification | verify | Low- and high-resolution checks and their results |

## The skills

### signalflag-onboard

The entry point. Interviews, writes the brief, names the next skills.

**Reads, in order:** existing tests and harnesses (pytest, eval scripts, CI,
grading notebooks) → the experiment runner → artifacts on disk → the user.
Harness constructs map directly:

| Harness | SignalFlag |
|---|---|
| Test case / parametrize id | Test name |
| Scenario file / fixture | Experience |
| Assertion with a threshold | Status check |
| Value computed to assert on | Emitted metric |
| CI trigger | Integration form, and whether `version` is a commit |
| Logged, never asserted | Data-first for that data |

**Interviews from a concrete run, not from vocabulary.** Opens with "pick a run
you did recently — where did its files go and what did you look at after?",
reads those files, and plays them back in the user's words. SignalFlag terms
appear only as a picture of their own data. One question per message; each
question carries the agent's best guess.

**Decides:**

- **Intent.** Metrics-first (knows the numbers) or data-first (emit everything,
  query later).
- **Shape**, from what they want to see:

  | Want | Shape | Constraint |
  |---|---|---|
  | Experiment / leaderboard over checkpoints, policies, sweeps | Natural batches and tests + a dashboard, or batch-level metrics for one batch | Everything on one dashboard is on one branch |
  | Repeated CI regression | One batch per build, test names from their suite | Same branch |
  | Data dump to explore | Wide generic topics, metrics later | Same branch |

  RL: evaluation per cycle as training runs → one batch per cycle on one branch
  + dashboard. Finished checkpoints evaluated together → one batch, one test per
  checkpoint, batch-level ranking.
- **Integration**, from what exists:

  | Present | Form |
  |---|---|
  | Sim harness / suite runner | Harness: SignalFlag wired into the runner |
  | Local test harness | Hook: `conftest.py` plugin or eval wrapper |
  | Loose artifacts, no harness | Script: ingest over run folders (+ structure-runs only if metadata is missing) |
  | Existing results, shown once | One-off |

- **Control level** for metrics and events.

**Never guesses the branch or test names.** Both are confirmed by the user:
schemas are additive-only per branch, and branch decides what can be charted
together. Test names come from the user's suite; they are never invented to fit
A/B comparison.

**Done when** the user approves the brief. Names the next skills, skipping any
the brief makes unnecessary.

### signalflag-model

SignalFlag's object model for a customer: project, branch, batch, test,
experience, version, metrics set, dashboard. What compares with what: batch
comparison pairs same-named tests; multi-run and checkpoint comparison is a
dashboard; dashboards and reports read one branch.

**Exists only if baseline tests show agents mis-mapping without it.** Otherwise
folded into onboard.

### signalflag-auth

- `scripts/check_token.py`: no network. Reads the token cache (with the legacy
  fallback), applies the SDK's 1 h margin, prints valid-until / expired /
  missing, exit code to match.
- `scripts/login.py`: says a URL is coming and to open it, then
  `DeviceCodeClient()`. The agent asks the user to run it as
  `! python <path>/login.py` so the URL lands in their session.
- MCP: checks `signalflag` is connected; if not, gives the `claude mcp add` line and
  `/mcp` to authenticate.
- Every skill that calls the API runs it first.

### signalflag-structure-runs

Only when onboard finds the artifacts cannot answer what ingest needs.

- One folder per run, `run.json` beside the artifacts, fields the brief names
  (typically run name, version under test, params, seed, grader version, time
  basis, start time).
- One `write_manifest(run_dir, **fields)` call where the runner already knows
  those values. No restructuring. The user's tests still pass.
- Backfills old runs where fields are recoverable; lists the ones it skipped.
- Done when ingest can fill every field without importing the runner.

### signalflag-design-metrics

What to measure and what moments matter. Writes the data profile and the
metrics plan.

**Control levels** (from the brief):

| Level | Agent | User | Review |
|---|---|---|---|
| Agent-led | Profiles data, builds metrics, charts, events | Reacts | Low-res verify batch |
| Partial | Profiles data, offers a menu grounded in it | Picks, edits | Menu, then low-res batch |
| User-led | Builds what's asked, flags what the data can't support | Specifies | Low-res batch |

**Levels:** `test` (one run), `batch` (all tests in a batch), `dashboard`
(batches over time on one branch, joined to `metadata`).

**Question → chart:**

| Question | Template | Columns |
|---|---|---|
| What actually ran | `video` / `image` (GIF) | attached filenames |
| How did X change during the run | `line` | `series, x, y` |
| How do categories, tests, builds compare | `bar` | `group_name, x, y`, optional `link_path` |
| Ranking, leaderboard, many values per row | `table` | any |
| Headline number | `scalar` | `value` |
| Which mode, when | `state_timeline` | `system, timestamp, state` |
| How is X spread | `histogram` | values |
| Share of one whole, ≤ 6 slices | `pie` | `category, value` |
| Anything else | custom template | see compose-metrics |

**Disciplines:**

1. **What ran comes first.** Any scene or front camera becomes a GIF or video,
   the first metric on the test page. Page order: what ran → verdict →
   evidence → raw.
2. **Emit wide, chart narrow.** Everything readable goes to the data lake; the
   metrics set shows only what answers the brief.
3. **5–20 metrics per page.** A scalar takes a placard as large as a line chart,
   so related headline numbers go in one table, not a row of scalars.
4. **Agent-led uses a spread of templates**, not twenty line charts.
5. **No chart without a question in the brief.**
6. **Emit the margin, not only the verdict**, so a chart shows how close it came.
7. **Distributions, not just means**, once there are more than a handful of
   tests; tails (p90, max, worst test) for safety metrics.
8. **Every threshold states its source**: spec, measured percentile, or user.
9. **Units on every metric.**
10. **A leaderboard is a `table` or `bar`** at batch or dashboard level, sorted
    by the user's metric.
11. **One-line descriptions.**

**Events**, judged here with the same control level:

- Auto-emitted unless the user opts out: first crossing of a `warn`/`block`
  threshold (backed by the chart around it); each change in a state-timeline
  topic; harness failures — exception, timeout, failed assertion (backed by the
  log excerpt).
- User-named moments on top.

`catalog.md`: starter metrics by domain — navigation, manipulation, perception,
RL training and evaluation, sim health (RTF, dropped messages). Proposed only
where the data supports them.

### signalflag-compose-metrics

Turns the metrics plan into `.resim/metrics/config.resim.yml` and
`templates/*.liquid`. Short SKILL.md; syntax in `config-reference.md` and
`templates.md`.

- **Topics:** `boolean, int, float, string, status, image, video, string[],
  metric[]`. Event topics: `event: true`, schema `name, description, status,
  tags, metrics: metric[]`, where each metric is `{name, type, value,
  status?}`, `type` ∈ scalar, image, plotly, text, video, artifact. Data-first:
  long-format `(name, value)` topics.
- **Metrics:** `query_string`, `type`, `template_type`, `template` /
  `template_file`, `template_settings`, `units`, `description`,
  `skip_if_no_data: true` on every metric, `status` (`query_string` with `?`,
  `warn`, `block`).
- **`metadata` table** for batch, job, branch, build, experience, status, tags,
  custom fields; `build_version` groups dashboards by version.
- **SQL** is Presto/Trino-style (`ARBITRARY()`); alias every column to its
  template's contract.
- **Metrics sets**; multiple config files merge if each topic appears once.
- **Escape hatches** when SQL and system templates can't express a chart:
  - The test builds a Plotly figure and emits it as a `raw_metric: string`;
    an empty `raw.liquid` passes it through.
  - A Liquid template reshapes query columns into a Plotly chart (e.g.
    `strip.liquid`, a box/strip plot).
- **Traps:** schemas additive-only per branch, topic archiving irreversible —
  prototype on a scratch branch. Rejections carry no line number (`bar` not
  `bar_chart`, `float` not `double`). Batch SQL selects `experience_name` from
  the topic; joining `metadata` for it fails opaquely. No CLI debug; the local
  check is the Emitter's validation, then verify's low-res batch.

### signalflag-ingest

**Readers and uploader stay apart.** A reader turns an artifact into rows and
never imports `signalflag`. The uploader turns rows into SDK calls and never
parses a file. Every mode reuses the same readers.

| Mode | Writes | Batch per | Test per |
|---|---|---|---|
| Harness | Module the runner calls | Runner invocation | Case |
| Hook | `conftest.py` plugin / eval wrapper | Session | Test case |
| Script | `ingest_<topic>.py` | Invocation | Run folder |
| One-off | Script, run once | Once | Artifact |

**Every mode has a low-res option** (`--max-tests`, `--stride`, `--no-media`
except the summary GIF, `--branch`). Verify and iterate depend on it.

**Rules:**

- **Dependencies** (`signalflag`, and each reader's `mcap`, `pandas`, `h5py`,
  ...) follow where the code lives:
  - **Separate from their codebase** (script, one-off): installed only into a
    dedicated venv, pinned in the ingest's own `requirements.txt`. Nothing is
    downloaded outside a venv — not into system Python, not into the user's
    environment. The ingest stays self-contained (own requirements, one entry
    point) so a later container image is a thin wrapper around it.
  - **Inside their codebase** (harness, hook, runner emission): added the way
    that codebase adds dependencies — its manager (pyproject, uv, poetry,
    requirements, conda, Bazel, ROS `package.xml`), as an optional extra or
    dev group where it has one.
- Auth via `DeviceCodeClient()` after signalflag-auth confirms a token.
- Raw artifacts are attached by default; the brief lists which.
- A test that ran and fell short is a failure, not an error: in hook mode the
  assertion must not escape `with Test(...)`. Emit the value; the status check
  decides.
- Emitted media `filename` equals the `attach_log` basename; ≤ 100 referenced
  files per run.
- Timestamps in ns, basis stated. For mcaps, header stamps are sim time, log
  time is receive time.
- Run from a temp dir or clean up `emissions_*.resim.jsonl`.

`events.md`: detectors as pure functions rows → events; `emit_event(topic,
data, timestamp)` with one timestamp; attaching the backing clip or metric in
`metrics`.

`readers/*.md`: per format, rows out, columns → `emit_series`, that format's
traps. A new format is a new file.

### signalflag-verify

**Low resolution**, scratch branch, via ingest's low-res option: ~3 tests,
strided series, a downscaled summary GIF. Checks: `Batch` opened (config
synced), every emit validated, every job SUCCEEDED, no `LogUploadError`, and
via the MCP every metric in the set has data with the statuses the brief
expects. Hands the user the batch link; this is where agent-led and partial
users review.

**High resolution**, the real branch, full data. Checks: test and event counts
match the source, spot-checked metric values match values computed locally from
the reader rows, the dashboard picks up the batch. Results go in the brief.

A failed check is fixed at its cause — reader, config, uploader — before moving
on.

### signalflag-iterate

For the agent's own experiments: repeatedly changing the user's code against a
test type that has a brief.

Loop: change → run → ingest low-res to the campaign branch with `version` = the
commit (or a label for uncommitted work) and a one-line batch name saying what
changed → read back through the MCP → compare with the previous iteration →
decide. One branch per campaign, so every attempt lands on one dashboard and the
summary videos and headline metrics show the progression. High-res only for a
candidate worth keeping.

The MCP read-back steps are written against the MCP's real tools during
testing, not assumed.

## Testing

Each skill is built with superpowers:writing-skills: baseline scenario without
the skill, watch it fail, write the skill against the observed failures, re-run,
close loopholes. One skill at a time, in dependency order:

1. auth
2. onboard (+ the model question below)
3. design-metrics
4. compose-metrics
5. ingest
6. structure-runs
7. verify
8. iterate

Scenarios use real inputs from this repo where possible (the M6 sweep run
folders, the perception replay bags, the grading harness) and synthetic
fixtures for the rest (an RL checkpoint directory, a parquet dump, a pytest
suite with thresholds).

**The model question:** baseline agents without signalflag-model map an RL
checkpoint comparison and a pytest suite. If they invent test names, split one
dashboard's data across branches, or force a leaderboard into A/B comparison,
signalflag-model is written from those failures. If not, its content folds into
onboard.

## Retiring /resim-run

Delete `.claude/skills/resim-run/` here once signalflag-ingest and
signalflag-verify pass their tests. Copies in other local repos are
the user's call.

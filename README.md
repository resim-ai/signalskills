# signalskills

Claude Code skills for getting experiment and simulation results into [SignalFlag](https://signalflag.ai) (formerly ReSim) through its Python SDK. They're written for engineers who don't know SignalFlag's object model. The agent reads their runs, asks about them, writes one brief per test type, then builds the metrics config and upload code and checks the numbers.

## Skills

| Skill | Does |
|---|---|
| `signalflag-onboard` | The entry point. It checks for an existing brief and asks one question first: *you decide* (only the project is asked) or *walk me through it* (options with a recommendation at each step). Then it writes the plan as `docs/signalflag/<test-type>-test-brief.md`. Today it routes to the SDK path; cloud runs will branch here later. |
| `signalflag-auth` | Checks the SDK's device-code token with `check_token.py`. The person runs `login.py` themselves. Finds the SignalFlag MCP by its tools. |
| `signalflag-design-metrics` | Profiles the data and writes the metrics plan: what ran first, 5–20 test metrics, margins, threshold sources, events. |
| `signalflag-compose-metrics` | Writes `.resim/metrics/config.resim.yml` and templates, validates and previews them, and proves them with a scratch-branch sync. |
| `signalflag-ingest` | Readers, event detectors and the uploader (Batch/Test/emit/attach_log) for mcap, parquet, csv, h5 and dataframes. Pushes low-res only. |
| `signalflag-verify` | Low-res pass on a scratch branch, with values recomputed from the source files, fixes at the cause, then one full push to the real branch. |
| `signalflag-iterate` | For the agent's own experiments: a campaign branch, one read-back batch per attempt, and a progression dashboard. |

The flow: onboard → design-metrics → (your go) → auth → compose-metrics → ingest → verify, then iterate for later changes. Nothing is installed, logged in or uploaded before your go.

## Install

As a Claude Code plugin (recommended). In Claude Code:

```
/plugin marketplace add resim-ai/signalskills
/plugin install signalskills@signalskills
```

This installs the seven skills and registers the SignalFlag MCP server (`https://bff.resim.ai/mcp`). Run `/mcp` once and sign in. Update later with `/plugin marketplace update signalskills`.

Or link the skills yourself, into a project's `.claude/skills/` or `~/.claude/skills/`:

```bash
git clone https://github.com/resim-ai/signalskills.git ~/signalskills
for s in ~/signalskills/skills/signalflag-*; do ln -s "$s" ~/.claude/skills/; done
claude mcp add --transport http -s user signalflag https://bff.resim.ai/mcp
```

The skills need `signalflag==1.8.0` in a venv. They create one when it's missing and never install outside a venv.

Installed it before under the old name `superflowers`? Remove it first, then install as above:

```
/plugin uninstall superflowers@superflowers
/plugin marketplace remove superflowers
```

## Use

Open Claude Code in the repo that has your runs, and ask in your own words, for example "Get our Isaac route tests into SignalFlag" or "Make my pytest run report to SignalFlag". `signalflag-onboard` starts there. It asks whether you want it to decide or to walk you through each choice, and it asks which project. When a login is needed, it posts a link for you to approve in the browser.

## Tests

Each skill was written test-first, following [superpowers:writing-skills](https://github.com/obra/superpowers). Fresh agents ran each scenario without the skill, then with it, and every gap they found became a rule. `tests/signalflag/<skill>/` holds `scenarios.md`, `baseline.md` (without the skill), `green.md` (with it) and `refactor.md` (loopholes closed).

```bash
cd tests/signalflag
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q auth tools           # script and tooling tests
bash tools/new_workspace.sh rl_project demo-1       # a fresh workspace from a synthetic fixture
```

The `rl_project`, `pytest_suite`, `parquet_dump` and `sim_runner` fixtures are synthetic (`tools/make_fixtures.py`). The `m6` and `replay` scenarios used private robot data. Their records are kept, but their fixtures aren't in this repo.

### Evals

Two end-to-end evals run the real skills headlessly (`claude -p` with only this plugin) against simulated engineers. A Claude persona answers from its facts, and a judge plus programmatic checks grade the result. Nothing is uploaded.

- `tests/signalflag/eval/onboard/`: 32 personas covering RL, imitation learning, perception, localization, behavior, test, fleet and data-QA work, from junior to lead, with mcap, ROS1, LeRobot, h5, parquet, video and pytest data. Graded on the interview and the brief.
- `tests/signalflag/eval/design-metrics/`: 23 cases that start from an approved brief, with faults planted in the fixture data. Graded on whether the plan catches each bad run and points to its cause, fits its reader, keeps to one metric per question, uses charts and media (video vs GIF), keeps events leveled and not spammy, and computes in Python what SQL can't.

```bash
cd tests/signalflag/eval/onboard && ../../.venv/bin/python run_eval.py --approve-harness   # once, after reviewing the harness
../../.venv/bin/python run_eval.py --variant baseline --reps 2                       # writes .claude/hillclimb/onboard/
```

A full onboarding pass costs about $125 in API calls (64 conversations). Cases drawn from real customer threads are anonymized patterns only.

`docs/design.md` is the spec and `docs/plan.md` the implementation plan.

## Releasing changes

Installed plugins update only when `version` in `.claude-plugin/plugin.json` changes. Claude Code compares that number, not the commits. So with every change users should get:

1. Bump `version`, following semver: patch for skill wording and fixes, minor for new skills or behaviour, major for breaking renames.
2. Run `claude plugin validate .`.
3. Commit and push to `main`.

Users then pick it up with:

```
/plugin marketplace update signalskills
/plugin update signalskills@signalskills
```

and restart Claude Code. If you push without bumping the version, people who already installed it keep the old copy.

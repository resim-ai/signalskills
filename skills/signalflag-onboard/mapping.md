# Mapping a team's work onto SignalFlag

## SignalFlag's objects, for translating (never lead with these)

| Object | What it is | Rule that bites |
|---|---|---|
| Project | Top-level container for an org's work | Already exists; ask which. Never create one silently. |
| Branch | A line of batches, like a git branch | **Dashboards and reports read one branch.** Schemas are additive-only per branch. |
| Batch | One upload: a set of tests, with a `version` | `version` is what makes one batch differ from the next |
| Test (= experience) | One item in a batch, matched by name | Two batches compare only tests with the same name |
| Dashboard | Charts across every batch on a branch | The way to rank or trend across runs, checkpoints, builds |
| System | The thing under test (a perception stack, a planner, the whole robot) | Tests are registered to it; batches name it. Must exist before a batch names it (created after the go). |
| Test suite | A named, revisioned set of tests for one system, with one metrics set | Batches of one suite compare like with like; a changed test list is a new revision. Built from tests that already exist, so it comes after the first push. |
| Metrics set | A named group of metrics in the config | Each batch (and each suite) evaluates one set. Different data or different questions → a different set. |

## Their harness already says a lot

| In their code | In SignalFlag |
|---|---|
| Test case / parametrize id | Test name |
| Scenario file / fixture | Experience |
| Assertion with a threshold | Status check (`warn`/`block`) |
| Value computed to assert on | Emitted metric |
| CI trigger | Integration form; `version` is probably the commit |
| Logged, never asserted | Data-first for that data |
| Written test case / procedure ID, repeated on robots or attempts | Test name = the case; repeats are fields inside it or tests — ask |

## Flavors of test: systems, suites, metrics sets

Ask once the shape is clear, in their words ("is the lidar replay the same stack as the camera one?"). Most single-harness projects are one system, one suite, one set: say so and move on.

| They have | System | Test suite | Metrics set |
|---|---|---|---|
| Different things under test (perception stack vs planner vs full robot) | one each | one or more per system | per system (their questions differ) |
| Same system, different modality or source (camera vs lidar; sim vs replay vs field) | one | one per modality | per modality when the data differs; shared when it's the same data |
| Regression tests (must pass) and known failures (tracked bugs, expected to fail) | one | two: `regression` gates the release; `known failures` tracks which now pass and never blocks | shared when the questions match, but the known-failures set carries no `block` statuses; separate when the known failures need diagnostics the regression set doesn't |
| One suite, several test types emitting different topics | one | one | a set per test type (or optional metrics) — see compose-metrics' required-vs-optional rule |

A test that moves from known failures to passing moves suites (a new revision of each) — record who owns that move. Branches still separate lines of comparison; a suite doesn't replace the branch.

## Shape follows what they want to see

| They want | Shape | Constraint |
|---|---|---|
| Experiment / leaderboard: checkpoints, policies, sweeps, ranked by chosen metrics | Natural batches and tests + a **dashboard**; or batch-level metrics when it's all one batch | Everything on one dashboard is on one branch |
| Repeated CI regression: same suite, build after build | One batch per build, test names from their suite | Same branch |
| Data dump to explore later | Wide, generic topics; metrics added later as SQL | Same branch |

RL, two cases — ask which:
- Evaluated **as training runs** → one batch per evaluation cycle, `version` = step, one branch, a dashboard ranks and trends.
- Finished checkpoints **evaluated together** → one batch, one test per checkpoint, batch-level ranking table.

## Integration follows what exists

| Present | Form | Where the code goes |
|---|---|---|
| Sim harness / suite runner (containerised too) | **harness** — SignalFlag wired into the runner | Their runner; an image without the SDK → the runner's host-side entry point, per run |
| Local test harness (pytest, eval script) | **hook** — `conftest.py` plugin or eval wrapper | Their repo; dependency via their manager (pyproject extra, etc.) |
| Loose artifacts, no harness | **script** — ingest over run folders, re-run on new results | Separate; own venv |
| Existing results, shown once | **one-off** | Separate; own venv |

`structure-runs needed: yes` only when the artifacts can't answer what ingest needs — e.g. an eval folder that doesn't record which checkpoint produced it. Otherwise no.

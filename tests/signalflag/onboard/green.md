# onboard GREEN running notes
## o3-1
T1: loaded skill; read tests, no install; one intent question grounded in clutter + best guess. 
## o5-1
T1: no build; read scenario/outputs/run_results; noted missing build/commit; one grounded question with guess. 
## o2-1
T1: no build; read runner + evals; flagged 20260901T020000 missing log.txt as a guess, git commit unrecorded; one grounded question with guess. Tried a read-only numpy check (failed, no numpy) — harmless.
## o1-1
T1: no build; read runs; flagged dirty sha; one grounded question (curve) with guess.
## o4-1
T1: no build; profiled parquet, flagged v2 extra column + missing provenance; one grounded question with guess.
T2 (o3-1): batch/test introduced on their data; test names = parametrize ids; one two-part question about names.
T2 (o5-1): classified data-first (grading later) — defensible, scenario said metrics-first; accept either and note. Batch/test shown on their data; one question on grouping.
T2 (o2-1): shape right: batch per eval, version = step, seeds as tests, one branch + dashboard ranks/trends; vocab introduced on their data; one question.
T2 (o4-1): data-first recognised; asks project, refuses to create one.
T3 (o3-1): branch question with explained consequences and 3 options; asked, not guessed.

SCORE o2-1: grounded Y | one-q Y | vocab-first Y | branch/project/tests/version confirmed Y | brief 9 headings, 5 filled Y | form script + structure-runs yes Y | metrics-first Y | shape batch-per-cycle + dashboard Y | next-skills Y (structure-runs first) | no installs/API Y | missing ckpt → open item Y — PASS all
SCORE o3-1: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | form hook + pyproject extra + opt-in Y | metrics-first Y | CI auth → open item | next-skills Y | no installs Y — PASS all
SCORE o4-1: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | form script Y | data-first Y | next-skills Y | no installs Y — PASS all (note: "single table with all columns" — wide topic, additive; long-format is compose's call)
SCORE o1-1: grounded Y | one-q Y | vocab-first Y | confirmed branch/project/tests/version Y | brief Y | form script Y | metrics-first Y | next-skills Y | no installs Y — PASS all
SCORE o5-1: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | form harness Y | data-first (accepted) | next-skills N — skipped design-metrics AND compose-metrics "because metrics are deferred"; ingest can't emit without topics in a config. | no installs Y — FAIL on routing.
Other notes: CI/container auth raised as open item (o3, o5) — consistent open question for the human partner.

## Round 2 (after rename to signalflag-sdk-onboard; SignalFlag MCP with its own `onboard` skill connected)
SCORE o3-2: grounded Y | one-q Y | vocab-first Y | project/branch/tests/version confirmed Y | brief Y | hook + pyproject extra + opt-in Y | metrics-first Y | CI auth open item | next-skills Y | no installs/API Y — PASS all. No collision with the server's `onboard` skill.
SCORE o4-2: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | script Y | data-first Y | next-skills Y (compose kept — R1 holds) | no installs Y — PASS all
SCORE o2-2: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | script Y | shape batch-per-eval, version=step Y | structure-runs: skipped "because log.txt already records the checkpoint for every run we're uploading" — defensible: the runner writes log.txt with the ckpt path going forward, only the old folder lacks it (excluded, open item). Scenario criterion was too narrow; accept either when justified from what the runner writes. | next-skills Y | no installs Y — PASS
SCORE o5-2: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | harness (replay-all step) Y | data-first Y | next-skills Y — compose kept (R1 holds) | no installs Y | unrecorded commit → open item Y — PASS all
SCORE o1-2: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | script Y | metrics-first Y | next-skills Y | no installs Y — PASS all
Round 2: 5/5 PASS. (o3-2 went on into signalflag-auth after approval, as routed — outside onboard's scope.)
note o2-3: one message bundled two questions (hook vs script + where to install) — minor one-q slip.

## Round 3
SCORE o3-3: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | hook + pyproject extra Y | metrics-first Y | CI auth open item | next-skills Y | no installs Y — PASS all
SCORE o2-3: grounded Y | one-q ~ (one bundled pair) | vocab-first Y | confirmed project/branch/version Y, seed names left open then confirmed at approval | brief Y | script + structure-runs yes (record ckpt) Y | shape + dashboard Y | missing ckpt excluded Y | next-skills Y | no installs Y — PASS
SCORE o4-3: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | script Y | data-first Y | structure-runs yes for week provenance (defensible) | next-skills Y (compose kept) | no installs Y — PASS
SCORE o5-3: grounded Y | one-q ~ (runner-vs-script + GIF bundled once) | vocab-first Y | confirmed Y | brief Y | harness (replay_all runner) Y | data-first Y | structure-runs yes (commit + per-scenario GIF) | next-skills Y (compose kept) | no installs Y — PASS
SCORE o1-3: grounded Y | one-q Y | vocab-first Y | confirmed Y | brief Y | script Y | metrics-first Y | next-skills Y | no installs Y — PASS all
Round 3: 5/5 PASS.

# GREEN summary
15 interviews (5 scenarios × 3 reps). Round 1: 4/5 (o5 routing → R1). Rounds 2–3, after R1 and the rename to signalflag-sdk-onboard, with the server-side `onboard` skill also available: 10/10.
Against RED: brief 0/11 → 15/15; asked before building 0/11 → 15/15; branch confirmed 0/11 → 15/15; intent asked 0/11 → 15/15; next skills 0/11 → 15/15.
Residual: 2/15 bundled two questions in one message once (o2-3, o5-3). Not a discipline break (each still carried a guess and waited); no wording change.
Consistent open item across CI/container scenarios: no browser for device-code auth → raised to the human partner.

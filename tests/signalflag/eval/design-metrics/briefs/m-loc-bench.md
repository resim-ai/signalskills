# Localization benchmark (loc-bench) — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- **Runner:** `.github/workflows/loc-bench.yml`, on every `pull_request` and on push to `main` (ubuntu-22.04, Python 3.11, `pip install -r requirements.txt`).
  1. `python bench.py` runs `loc.estimator.run` (wheel odometry + scan-match complementary filter, `GAIN = 0.12`) over every folder in `sequences/`, writes `sequences/<seq>/estimate.txt`, and prints ATE/RPE to stdout.
  2. `pytest tests -q --junitxml=results/junit.xml` recomputes ATE/RPE per sequence (`tests/test_bench.py`, parametrized on `seq`) and asserts `ATE < 0.15 m` and `RPE < 0.05 m`.
  3. The `loc-bench` GitHub artifact holds `sequences/*/estimate.txt` and `results/`.
- **Sequences (4):** `corridor_long`, `ramp_up`, `warehouse_loop`, `yard_figure8`. Each one has:
  - `groundtruth.txt` and `estimate.txt`: TUM `t x y z qx qy qz qw`, 10 Hz, about 300 rows (30 s), planar (z = 0, yaw stored in qz/qw).
  - `odometry.csv`: `t,v_mps,w_radps` at 20 Hz, about 600 rows.
  - `scan_match.csv`: `t,x,y,yaw` at 2 Hz, about 60 rows.
- **Metrics code:** `loc/metrics.py` — ATE RMSE after rigid 2D SVD alignment, and RPE RMSE over 1 s segments (translation only). Both in metres.
- **Not recorded today:**
  - The ATE/RPE values. They are printed to the log and lost; junit keeps only pass/fail.
  - Which commit produced a run (it's only in the Actions run metadata).
  - The estimator parameters (`GAIN`). They live in code, so the commit identifies them.
  - Per-timestep error. It can be derived from estimate vs. groundtruth.
- `conftest.py` exists at the repo root and is empty.
- Size and frequency: tiny (about 5k text lines total). One run per PR push and per merge to `main`.

## Intent
- **Question:** "Did this PR make localization worse, on which sequence, and by how much, compared with `main`?" There's a second question too: how ATE/RPE trend across merges to `main`.
- **Who asks:** PR authors and reviewers of estimator changes.
- **Kind:** a CI regression gate. Pass/fail limits already exist in pytest, so SignalFlag adds the numbers, the history and the comparison.
- **Metrics-first.** The pytest assertions already name the quantities that matter.

## Control
- Mode: **A** (agent decides). Confirmed by user.
- Project: given by the user.
- Metrics and events: **user-led.** The user picks the metrics themself. The agent proposes what the data supports in design-metrics; the user chooses metrics, charts, thresholds and status checks. Nothing in that area is defaulted.
- Everything else (branch, batch, test, version, integration) is chosen by the agent and shown at the single go, before anything reaches SignalFlag.

## Mapping
In their words: every CI run of the benchmark checks 4 sequences, and each sequence gets an ATE and an RPE number. In SignalFlag terms, each CI run is one *batch* and each sequence is one *test*.

- Project: `acme-robotics` (confirmed by user: yes — already exists; don't create it)
- Branch: `loc-bench` (chosen by agent — this is a repeated CI regression on one suite. PR runs and `main` runs must share one SignalFlag branch so dashboards and comparisons see both. Git branch names are not used. The git ref/PR number goes in batch metadata, so `main` runs can be filtered as the baseline.)
- Batch is: one CI run of the `loc-bench` workflow (one PR push, or one push to `main`). Tags/metadata: git ref, PR number (if any), Actions run URL.
- Test is: the sequence folder name — `corridor_long`, `ramp_up`, `warehouse_loop`, `yard_figure8` (chosen by agent — this is the pytest `seq` parametrize id. ATE and RPE are two measurements of the same sequence run, so they become metrics on one test, not 8 separate tests. Names are stable, so batches compare test for test.)
- Version is: the commit under test — `github.event.pull_request.head.sha` on PRs, `GITHUB_SHA` on push (chosen by agent — on PRs, `GITHUB_SHA` is a throwaway merge commit, so the head SHA is what authors recognise. The commit also pins `GAIN` and other estimator parameters.)

## Integration
- Form: **hook** — a pytest plugin in the existing root `conftest.py`. pytest already runs on every PR and loads each sequence's groundtruth/estimate, so the upload happens as part of the step CI already runs. No change to `bench.py` or the workflow steps, other than passing credentials and env.
  - It uploads only when SignalFlag credentials are present in the environment (CI). Local `pytest` runs stay offline and unchanged.
  - Test pass/fail and the pytest exit code are unaffected. Any gating via SignalFlag status checks is the user's call (see Control).
- structure-runs needed: **no** — each sequence folder has both groundtruth and estimate, and the commit/ref comes from the GitHub Actions env. Nothing that ingest needs is missing.
- Environment: the repo's own `requirements.txt` (no pyproject). The SignalFlag SDK gets added there; CI installs it via the existing `pip install -r requirements.txt`. Locally, use a venv, e.g. `.venv/`.
- **Open items:**
  - CI credentials: the device-code login can't run in Actions. A non-interactive credential has to be stored as a repo secret (e.g. `SIGNALFLAG_*`) and passed to the pytest step. Resolve at signalflag-auth, after the go.
  - PRs from forks don't receive secrets. Those runs will skip upload; this is acceptable unless the user says otherwise.
  - The workflow file needs an `env:` block on the pytest step for the secret and the PR head SHA. This is the only workflow edit.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

# HIL motor bench (pytest) — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- **Harness:** pytest suite `tests/hil/test_motor.py`, marker `hil`. It drives an MC4 motor controller over serial (`bench/link.py`, `/dev/ttyACM0`, 921600 baud), or the plant model with `--hil-backend=sim` (`bench/sim.py`).
- **Runner:** Jenkins (`Jenkinsfile`) on agent `hil-bench-01`: `rm -rf out && .venv/bin/pytest tests/hil -m hil --junitxml=out/junit.xml`. Then `junit` and `archiveArtifacts out/**`. Venv built from `requirements.txt` on every build. No trigger/schedule is set in the Jenkinsfile.
- **Tests (6):** `test_step_response[500rpm|1500rpm|3000rpm]`, `test_current_limit`, `test_reverse`, `test_stall_detect`.
- **Artifacts per run (`out/`, a few KB):**
  - `out/<test node name>/trace.csv`: `t_s, current_a, velocity_rpm, fault`, sampled every 2 ms. 200–500 rows per test (0.4–1.0 s), written at teardown by the `trace` fixture. `t_s` is controller time, monotonic across the session (not reset per test).
  - `out/device.json`: controller identity from `ID?` (model, serial, firmware, hw_rev, bootloader).
  - `out/junit.xml`: pass/fail, duration and the assertion message per test. The sample run has 1 failure: `test_step_response[3000rpm]`, rise time 0.134 s vs 0.120 s.
- **Computed but never recorded:** rise time (10–90 %), peak velocity/overshoot, peak |current|, final reverse velocity, stall-fault latency. These exist only inside the assertions.
- **Not recorded anywhere:** which backend ran (serial vs sim), the git commit / dirty tree, the Jenkins build number, and the test thresholds (`RISE_TIME_MAX_S`, `OVERSHOOT_MAX`, `CURRENT_LIMIT_A`).
- **Fixture inconsistency (open):** the sample `out/` mixes sources. `junit.xml` has `hostname=hil-bench-01` and a `bench.sim.SimController` repr in the failure. `device.json` says serial `MC4-00172` and carries a `port` key, but the current conftest can't write that key (the sim would report `MC4-SIM`). So the sample is not one coherent run. It's fine for profiling the data shape, but don't trust it as a hardware baseline.

## Intent
- **Question:** "Did this build, or this controller firmware, change how the motor behaves on the bench? Which of rise time, overshoot, current limiting, reversal and stall detection got worse, and by how much?" The goal is to trend values against the thresholds, not just see pass/fail. The 3000 rpm rise time is already 12 % over its limit, and `bench/sim.py` notes that firmware 2.7 softened the velocity loop.
- **Who:** the controls/firmware engineers who own the MC4 and this bench.
- **Kind:** a CI regression gate: the same suite, build after build.
- **Metrics-first:** the suite already defines what matters (its assertions). Full traces also go up so failures can be inspected without digging through Jenkins artifacts.

## Control
- Mode: **A** (agent decides). One stop: after the metrics plan, before anything reaches SignalFlag.
- Metrics and events: **agent-led**, seeded from the suite's existing assertions and thresholds.

## Mapping
In their words: one Jenkins build of the HIL suite on the bench → one *batch*. Each pytest case (including each rpm parametrization) → one *test*. Its trace → that test's time series. Its asserted values → *metrics*. Its thresholds → *status checks*.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `hil-motor`. Confirmed by user: yes. Note: the local git branch is `master`, so this is a SignalFlag branch name, not tied to git. **Hardware runs only.** Sim runs (`--hil-backend=sim`) would mix plant-model numbers into the hardware trend, so the hook sends them to `hil-motor-sim` (chosen by agent — keeps the hardware dashboard clean, and sim stays available for trying the hook without the bench).
- Batch is: one pytest session, i.e. one Jenkins build (chosen by agent — the Jenkinsfile runs one session per build).
- Test is: the pytest node name, e.g. `test_step_response[3000rpm]`, `test_stall_detect` (chosen by agent — already stable and unique, matches the `out/<test>/` folder and the Jenkins junit view, and parametrize ids keep the rpm in the name).
- Version is: `fw<firmware>-<git short sha>`, e.g. `fw2.7.1-edc5671`, with `-dirty` appended for an unclean tree (chosen by agent — behaviour depends on both the controller firmware and the test/bench code, and either can change between builds). Batch metadata also carries the full commit, firmware, controller serial, hw_rev, bootloader, backend, Jenkins `BUILD_NUMBER`/`BUILD_URL` when present, and hostname.

## Integration
- Form: **hook**: a pytest plugin in `tests/hil/conftest.py`, alongside the existing `controller`/`trace` fixtures. It collects each test's samples and outcome and builds one batch at session end. It's opt-in (e.g. `--signalflag` flag or `SIGNALFLAG_UPLOAD=1`), so local developer runs don't upload by default. The Jenkinsfile's HIL stage turns it on. Upload failures must not fail the HIL build.
- structure-runs needed: **no**. The hook runs in-process, so it has the samples, outcome, backend, firmware and commit directly, which covers everything the artifacts leave out. `out/` stays exactly as today for Jenkins.
- Environment: the repo's `requirements.txt` (add the SignalFlag SDK), installed into Jenkins' `.venv` by the Setup stage.
- **Open items:**
  - CI credentials: `hil-bench-01` needs a non-interactive SignalFlag credential (Jenkins credentials binding). Resolve at signalflag-auth.
  - Sample `out/` is mixed sim/hardware (see Current state). The first verified push should come from a real bench build, or from an explicit `--hil-backend=sim` run going to `hil-motor-sim`.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

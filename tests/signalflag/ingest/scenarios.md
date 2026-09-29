# signalflag-ingest scenarios

Workspace + brief (docs/signalflag/) + its config (.resim/metrics/) + a valid token in `<ws>/home`. Prefix:
> Work only inside <ws>. Run every shell command with `HOME=<ws>/home` set. I'm the user; I'll answer your messages. You may upload to SignalFlag, but only to project skilltest-project and only to the branch `skilltest-ingest-20260928-<scenario>-<rep>` — use it in place of the brief's branch. Don't attach bag (.mcap) files (network budget); everything else as the brief says.

## I1 — script over mcap runs (m6; briefs/c1.md; configs/m6)
Prompt: "Build the ingest from the brief and push the three runs."
## I2 — hook (pytest_suite; briefs/pytest.md; configs/pytest)
Prompt: "Make my pytest run report to SignalFlag, then run it once so I can see it."
## I3 — harness, 150 frames per scenario (sim_runner; briefs/sim.md; configs/sim)
Prompt: "Wire SignalFlag into run_suite.py so every suite run reports, then run it once with --gain 0.8."
## I4 — one-off (parquet_dump incl. telemetry_v2; briefs/c2.md; configs/parquet)
Prompt: "Just push the telemetry once."

## Pass
- Readers never import signalflag; the uploader never parses files.
- Low-res flags exist and work (`--max-tests`, `--stride`, `--no-media` keeping the summary media, `--branch`).
- Dependencies: I1/I3/I4 a dedicated venv + pinned requirements.txt; I2 the pyproject extra. Nothing installed outside a venv.
- `check_token.py` before any API call; DeviceCodeClient; no credential files.
- I1: series stamped from header (sim) time; emitted span per test within 10% of the bag's header-stamp span.
- I2: `clutter` (fails its assert) closes SUCCEEDED with its values emitted; the failing assert doesn't escape `with Test(...)`.
- I3: frames aggregated into one GIF per scenario; ≤ 100 referenced media files per run.
- Media `filename` emitted == attach_log basename.
- No `emissions_*.resim.jsonl` left in the workspace root.
- Auto events from the plan emitted with `emit_event` and one timestamp.
- Push succeeds: batch link printed, jobs closed, no LogUploadError.

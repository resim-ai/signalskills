---
name: signalflag-ingest
description: Use when a SignalFlag (formerly ReSim) brief's Config is filled and the upload code is next — a script over run folders, a pytest/conftest hook, emission calls in a sim or suite runner, or a one-off push of mcaps, csv, parquet, h5 or dataframes with Batch, Test, emit, emit_series, emit_event or attach_log.
---

# signalflag-ingest

Writes the code that gets the brief's data in. **REQUIRED:** `signalflag-auth` first.

## The shape

```
readers/     artifact -> rows      # never imports signalflag; one per format; readers/*.md
events.py    rows -> events        # pure functions; events.md
upload.py    rows -> Batch/Test/emit/attach_log   # parses nothing
```

The CLI or hook always takes

`--branch B  --version V  --max-tests N  --stride K  --no-media`

`--no-media` keeps the one summary GIF/video per test, downscaled (≤ 2 MB). In a pytest hook, prefix them `--sf-` (pytest owns `--version`).

| Brief's form | Code goes | Batch per | Test per |
|---|---|---|---|
| harness | a module the runner calls | invocation | case |
| hook | `conftest.py` plugin, opt-in env var | pytest session | test id |
| script | `ingest_<topic>.py` | invocation | run folder |
| one-off | the script, run once | once | artifact |

## Upload skeleton

```python
from signalflag.sdk.auth import DeviceCodeClient
from signalflag.sdk.batch import Batch
from signalflag.sdk.test import Test, LogType

if subprocess.run([sys.executable, CHECK_TOKEN]).returncode:   # signalflag-auth's check_token.py
    sys.exit("run signalflag-auth")    # DeviceCodeClient() would start a login here
client = DeviceCodeClient()
cfg = ROOT / ".resim/metrics"          # absolute, so a temp cwd keeps validation
with Batch(client, project_name=P, branch=B, version=V, name=N, metrics_set_name=S,   # S from the brief
           system=SYS, test_suite=SUITE,          # from the brief; omit until they exist (below)
           metrics_config_path=str(cfg / "config.resim.yml"), templates_path=str(cfg / "templates")) as batch:
    for run in runs[:max_tests]:
        with Test(client, batch, name=run.test_name) as t:   # same name => same experience
            t.emit_series("tracking", {"err_m": errs[::stride]}, timestamps=ts[::stride])
            t.attach_log(str(gif), LogType.OTHER_LOG)
            t.emit("replay", {"filename": gif.name}, ts[0])   # basename; column typed image (GIF)
print(f"https://app.signalflag.ai/projects/{batch.project_id}/batches/{batch.id}")
```

## Systems and test suites

When the brief names them: after the go, create the system with the MCP's `upsert_system` (by name; safe to repeat). A suite is built from existing tests, so push the first low-res batch without `test_suite`, register its tests on the system (`add_system_experiences`), create the suite (`create_test_suite`: system, test ids, the brief's metrics set), then pass `test_suite=` (and `test_suite_revision=` to pin) on later batches. A test that changes suites is a `revise_test_suite`, never an edit of an old revision. Not yet proven end to end on the server: check the first suite-attached batch reads back before relying on it.

## Rules

- **Dependencies:** separate script → own venv + pinned `requirements.txt`; inside their code → their manager (pyproject extra). Nothing outside a venv.
- **Never start a login from the runner or hook.** CI without a browser is an open item for the human, not a password fallback.
- **Keep the Emitter's validation on.** A rejected row means the config is wrong — fix it with `signalflag-compose-metrics`.
- **Time:** nanoseconds, sim time when sim time exists (mcap `header.stamp`, not `log_time`).
- **Media:** ≤ 100 files per test — frames become one GIF/video; emitted `filename` = the `attach_log` basename.
- **A test that fell short is a failure, not an error:** emit its values; status checks decide. Only real exceptions escape `with Test(...)`.
- **Emissions files:** `Test` writes `emissions_*.resim.jsonl` into cwd — use a temp dir (with the absolute paths above).
- **Push low-res only**, to a fresh `<branch>-lowres-<hhmm>`, and read it back through the SignalFlag MCP (`get_batch`, `get_metrics_summary`): any `RENDER_ERROR`/`QUERY_ERROR` goes to compose-metrics. "Push it once" means once to their branch — and that one push is verify's.

Done when the low-res batch reads back clean and its link is printed. Next: `signalflag-verify`, which owns the full push.

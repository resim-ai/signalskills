"""Upload each pytest session to SignalFlag. Opt-in: SIGNALFLAG_UPLOAD=1."""
import os, subprocess, tempfile, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent
UPLOAD = os.environ.get("SIGNALFLAG_UPLOAD") == "1"
PROJECT, BRANCH, METRICS_SET = "acme-sim", os.environ.get("SIGNALFLAG_BRANCH", "sim-int"), "Sim Integration"
_sf = {}

def _git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "unknown"

def pytest_sessionstart(session):
    if not UPLOAD:
        return
    from signalflag.sdk.auth import DeviceCodeClient
    from signalflag.sdk.batch import Batch
    _sf["client"] = DeviceCodeClient()
    _sf["tmp"] = tempfile.mkdtemp(prefix="signalflag-")
    _sf["batch"] = Batch(_sf["client"], project_name=PROJECT, branch=BRANCH, version=_git_sha(),
                         name=f"pytest {time.strftime('%Y-%m-%d %H:%M')}", metrics_set_name=METRICS_SET,
                         metrics_config_path=str(ROOT / ".resim/metrics/config.resim.yml"),
                         templates_path=str(ROOT / ".resim/metrics/templates"))
    _sf["batch"].__enter__()

def pytest_sessionfinish(session, exitstatus):
    if "batch" in _sf:
        _sf["batch"].__exit__(None, None, None)
        b = _sf["batch"]
        print(f"\nSignalFlag batch: https://app.signalflag.ai/projects/{b.project_id}/batches/{b.id}")

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    rep = (yield).get_result()
    if rep.when == "call":
        item.sf_report = rep

@pytest.fixture(autouse=True)
def signalflag_test(request, bus):
    """One SignalFlag Test per pytest test; every bus message is emitted to its topic."""
    if not UPLOAD:
        yield None
        return
    from signalflag.sdk.test import Test
    cwd = os.getcwd()
    os.chdir(_sf["tmp"])  # emissions files go to cwd
    t = Test(_sf["client"], _sf["batch"], name=request.node.name)
    t.__enter__()
    os.chdir(cwd)
    bus.subscribe(lambda topic, stamp_ns, msg: t.emit(topic, msg, stamp_ns))
    yield t
    rep = getattr(request.node, "sf_report", None)
    t.emit("test_result", {"test": request.node.name, "passed": bool(rep and rep.passed),
                           "duration_s": float(rep.duration if rep else 0.0)}, time.time_ns())
    os.chdir(_sf["tmp"])
    t.__exit__(None, None, None)
    os.chdir(cwd)

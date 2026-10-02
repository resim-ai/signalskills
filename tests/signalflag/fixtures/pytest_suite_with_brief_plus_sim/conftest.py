"""SignalFlag upload for the planner suite. Opt-in: SIGNALFLAG_UPLOAD=1 (needs `pip install -e .[signalflag]`)."""
import os, subprocess, tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent
CFG = ROOT / ".resim" / "metrics"
ENABLED = os.environ.get("SIGNALFLAG_UPLOAD") == "1"
_results = {}

def pytest_addoption(parser):
    g = parser.getgroup("signalflag")
    g.addoption("--sf-branch", default="planner-ci")
    g.addoption("--sf-version", default=None)

@pytest.fixture
def record_result(request):
    def record(result):
        _results[request.node.callspec.id] = (result, request.node)
    return record

def _version() -> str:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return sha + ("-dirty" if dirty else "")

def pytest_sessionfinish(session, exitstatus):
    if not ENABLED or not _results:
        return
    from signalflag.sdk.auth import DeviceCodeClient
    from signalflag.sdk.batch import Batch
    from signalflag.sdk.test import Test
    opt = session.config.getoption
    client = DeviceCodeClient()
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)  # Test writes emissions files into cwd
        with Batch(client, project_name="acme-robotics", branch=opt("--sf-branch"), version=opt("--sf-version") or _version(),
                   metrics_set_name="Planner Tests", metrics_config_path=str(CFG / "config.resim.yml"),
                   templates_path=str(CFG / "templates")) as batch:
            for scenario, (r, node) in sorted(_results.items()):
                ratio, margin = r.path_length_m / r.straight_m, r.min_clearance_m - 0.25
                with Test(client, batch, name=scenario) as t:
                    t.emit("plan_result", {"scenario": scenario, "path_length_m": r.path_length_m, "straight_m": r.straight_m,
                                           "min_clearance_m": r.min_clearance_m, "path_ratio": ratio,
                                           "clearance_margin_m": margin, "passed": ratio < 1.2 and margin > 0}, 0)
        os.chdir(cwd)
        print(f"\nSignalFlag: https://app.signalflag.ai/projects/{batch.project_id}/batches/{batch.id}")

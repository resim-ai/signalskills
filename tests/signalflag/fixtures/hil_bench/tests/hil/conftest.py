import csv, json
from pathlib import Path
import pytest

OUT = Path("out")

def pytest_addoption(parser):
    parser.addoption("--hil-port", default="/dev/ttyACM0")
    parser.addoption("--hil-backend", choices=["serial", "sim"], default="serial")

@pytest.fixture(scope="session")
def controller(request):
    if request.config.getoption("--hil-backend") == "sim":
        from bench.sim import SimController
        c = SimController()
    else:
        from bench.link import SerialController
        c = SerialController(request.config.getoption("--hil-port"))
    OUT.mkdir(exist_ok=True)
    (OUT / "device.json").write_text(json.dumps(c.identify(), indent=2) + "\n")
    yield c
    c.close()

@pytest.fixture
def trace(request, controller):
    """Call trace(n) to record n samples; written to out/<test>/trace.csv when the test ends."""
    rows = []
    def record(n):
        got = [controller.sample() for _ in range(n)]
        rows.extend(got)
        return got
    yield record
    d = OUT / request.node.name
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "trace.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "current_a", "velocity_rpm", "fault"])
        w.writerows(rows)

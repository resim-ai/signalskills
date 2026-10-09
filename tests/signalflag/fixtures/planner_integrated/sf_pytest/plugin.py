"""pytest plugin: one SignalFlag batch per session, one test per pytest item."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .records import TestRecord, planner_row

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / ".resim" / "metrics"
PROJECT = "acme-robotics"
DEFAULT_BRANCH = "planner-pytest"
METRICS_SET = "Planner Pytest"

_records: dict[str, TestRecord] = {}


def pytest_addoption(parser):
    g = parser.getgroup("signalflag", "SignalFlag upload (enable with SIGNALFLAG_UPLOAD=1)")
    g.addoption("--sf-branch", default=DEFAULT_BRANCH)
    g.addoption("--sf-version", default=None, help="default: git short SHA, -dirty if uncommitted")
    g.addoption("--sf-max-tests", type=int, default=None)
    g.addoption("--sf-stride", type=int, default=1, help="no series in this suite; accepted for uniformity")
    g.addoption("--sf-no-media", action="store_true", help="no media in this suite; accepted for uniformity")


def _enabled() -> bool:
    return os.environ.get("SIGNALFLAG_UPLOAD") == "1"


def _rec(item) -> TestRecord:
    return _records.setdefault(item.nodeid, TestRecord(name=item.name, start_ns=time.time_ns()))


@pytest.fixture
def signalflag_record(request):
    """Call with (scenario, result, obstacles, max_detour=..., min_clearance=...) before asserting."""
    def record(scenario, result, obstacles, *, max_detour, min_clearance):
        rec = _rec(request.node)
        rec.obstacles = [tuple(map(float, o)) for o in obstacles]
        rec.planner_result = planner_row(scenario, result, rec.obstacles, max_detour, min_clearance)
    return record


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    rec = _rec(item)
    if report.when == "call":
        rec.duration_s = report.duration
        rec.outcome = report.outcome
        if report.failed:
            rec.message = report.longreprtext
    elif report.failed:                       # setup/teardown error
        rec.outcome = "error"
        rec.message = report.longreprtext
    elif report.skipped and report.when == "setup":
        rec.outcome = "skipped"


def _git() -> tuple[str, bool]:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return sha, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def _token_ok() -> bool:
    """Stdlib check of the SDK's cached token; never starts a login."""
    import json
    home = Path.home()
    path = home / ".signalflag" / "token.json"
    if not path.exists() and (home / ".resim").is_dir():
        path = home / ".resim" / "token.json"
    try:
        at = datetime.fromisoformat(json.loads(path.read_text())["expires_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return (at - datetime.now(timezone.utc)).total_seconds() > 3600


def pytest_sessionfinish(session, exitstatus):
    if not _enabled() or not _records:
        return
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    say = (lambda m: tr.write_line(m)) if tr else print
    if not _token_ok():
        say("SignalFlag: no valid login token; skipping upload. Log in once with signalflag-auth's login.py.")
        return

    from signalflag.sdk.auth import DeviceCodeClient
    from signalflag.sdk.batch import Batch
    from signalflag.sdk.test import Test

    from .upload import emit_test

    opt = session.config.getoption
    sha, dirty = _git()
    version = opt("--sf-version") or (f"{sha}-dirty" if dirty else sha)
    recs = [r for r in _records.values() if r.outcome != "skipped"][: opt("--sf-max-tests")]

    client = DeviceCodeClient()
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)                         # Test writes emissions_*.jsonl into cwd
        try:
            with Batch(client, project_name=PROJECT, branch=opt("--sf-branch"), version=version,
                       name=f"planner-pytest {version}", metrics_set_name=METRICS_SET,
                       metrics_config_path=str(CFG / "config.resim.yml"),
                       templates_path=str(CFG / "templates")) as batch:
                for rec in recs:
                    with Test(client, batch, name=rec.name) as t:
                        emit_test(t, rec, sha, dirty)
        finally:
            os.chdir(cwd)
    say(f"SignalFlag: uploaded {len(recs)} tests to branch {opt('--sf-branch')!r}, version {version}")
    say(f"https://app.signalflag.ai/projects/{batch.project_id}/batches/{batch.id}")

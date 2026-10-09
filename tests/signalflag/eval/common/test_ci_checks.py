import pytest
from common.ci_checks import agents_fault, ci_problem, ci_target_problem

KNOWN = "FAILED tests/test_planner.py::test_plan[clutter] - assert 17.6 < (1.2 * 8.0)\n" \
        "tests/test_planner.py:11: AssertionError\n1 failed, 3 passed in 0.03s\n"


@pytest.mark.parametrize("name, out, changed, seed_main, agent", [
    ("traceback in plugin.py:502", "sf_pytest/plugin.py:502: in pytest_sessionfinish\n    KeyError: 'plan_ms'", (), False, True),
    ("traceback frame in hook code", 'File "/tmp/d/ci/sf_pytest/upload.py", line 40, in emit_test\nKeyError: x', (), False, True),
    ("HTTP 503", "httpx.HTTPStatusError: HTTP/1.1 503 Service Unavailable", ("sf_pytest/plugin.py",), False, False),
    ("bff non-200", "Exception: failed to run UpdateMetricsConfig 502: b'bad gateway'", (), False, False),
    ("requests 5xx", "requests.exceptions.HTTPError: 500 Server Error: Internal Server Error for url", (), False, False),
    ("network", "httpx.ConnectError: [Errno -3] Temporary failure in name resolution", (), False, False),
    ("token missing", "SignalFlag: no valid login token; skipping upload. Log in once with login.py.", (), False, False),
    ("config rejected", "Exception: [{'message': \"Failed to import config: column 'x' was removed\"}]", (), False, True),
    ("config rejected on seed main", "Exception: [{'message': 'Failed to import config: bad'}]", (), True, True),
    ("hook error on seed main is harness", 'File "/tmp/d/ci/sf_pytest/upload.py", line 4\nKeyError: x', (), True, False),
    ("collection error", "ERROR collecting tests/test_planner.py\nE   NameError: name 'x' is not defined", (), False, True),
    ("bare numbers are not status codes", "version 502abc uploaded 503 rows; timed out flag", (), False, False),
    ("unclassified, merged diff touched config", "something odd", (".resim/metrics/config.resim.yml",), False, True),
    ("unclassified, merged diff touched moved config", "something odd", ("ci/signalflag/metrics.yml",), False, True),
    ("unclassified, merged diff only brief", "something odd", ("docs/signalflag/brief.md",), False, False),
])
def test_agents_fault(name, out, changed, seed_main, agent):
    assert agents_fault(KNOWN + out + "\n[ci exit 1]", changed, seed_main) is agent, name


@pytest.mark.parametrize("plugin, problem", [
    ('PROJECT = "karthik-test"\nDEFAULT_BRANCH = "skilltest-um-x"\n', None),
    ('PROJECT = "acme-robotics"\nDEFAULT_BRANCH = "skilltest-um-x"\n', "PROJECT is not 'karthik-test'"),
    ('PROJECT = "karthik-test"\nDEFAULT_BRANCH = "planner-pytest"\n', "DEFAULT_BRANCH is not 'skilltest-um-x'"),
    ('PROJECT = "karthik-test"\nDEFAULT_BRANCH = os.environ.get("B", "skilltest-um-x")\n', "DEFAULT_BRANCH is not"),
    ('# PROJECT = "karthik-test"\nDEFAULT_BRANCH = "skilltest-um-x"\n', "PROJECT is not"),
])
def test_ci_target_problem(plugin, problem):
    got = ci_target_problem(plugin, "karthik-test", "skilltest-um-x")
    assert got is None if problem is None else (got and problem in got)


@pytest.mark.parametrize("out, problem", [
    ("SignalFlag: uploaded 4 tests to branch 'b1', version abc\n[ci exit 1]", None),
    ("SignalFlag: uploaded 4 tests to branch 'b1', version abc\n[ci exit 0]", None),
    ("SignalFlag: uploaded 4 tests to branch 'other', version abc\n[ci exit 1]", "no upload"),
    ("SignalFlag: uploaded 4 tests to branch 'b1'\n[ci exit 2]", "ci exit 2"),
])
def test_ci_problem(out, problem):
    got = ci_problem(out, "b1")
    assert got is None if problem is None else problem in got

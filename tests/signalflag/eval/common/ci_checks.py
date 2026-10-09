"""Reading a simulated CI run: did it upload where it should, and if it failed, whose fault was it (harness or agent)."""
import re

# The service, the network or the login: never the agent's change. Status codes only count when they come in an HTTP
# client / SDK message, not when the number just appears in output.
HARNESS_FAIL = re.compile(
    r"no valid login token"
    r"|HTTP[/ ]\S*\s*(?:401|403|429|50[0-4])\b"
    r"|status(?:_code)?[ =:]+(?:401|403|429|50[0-4])\b"
    r"|\b(?:401|403|429|50[0-4]) (?:Server Error|Client Error|Too Many Requests|Unauthorized|Forbidden|Bad Gateway"
    r"|Service Unavailable|Gateway Timeout|Internal Server Error)"
    r"|failed to run \w+ (?:401|403|429|50[0-4])\b"                       # signalflag.sdk.bff_client.graphql.post
    r"|httpx\.(?:ConnectError|ConnectTimeout|ReadTimeout|WriteTimeout|PoolTimeout|RemoteProtocolError|NetworkError)"
    r"|requests\.exceptions\.(?:ConnectionError|ConnectTimeout|ReadTimeout|Timeout)"
    r"|urllib3\.exceptions\.\w+|Max retries exceeded with url"
    r"|Temporary failure in name resolution|Name or service not known")

# Visibly the agent's change: the server rejecting the synced config, or the repo's own code failing.
AGENT_FAIL = re.compile(
    r"Failed to import config|Metrics config not found at|invalid metrics config|config validation failed"
    r"|ERROR collecting|INTERNALERROR.*(?:sf_pytest|conftest)"
    r"|(?:^|[\s\"/])(?:sf_pytest/\w+\.py|conftest\.py)[\":]"
    r"|\b(?:SyntaxError|ImportError|ModuleNotFoundError)\b|yaml\.(?:scanner|parser)\.", re.M)

# Files whose change can break the upload: the hook code and the synced metrics config (either location).
AGENT_PATHS = re.compile(r"^(?:sf_pytest/|conftest\.py$|\.resim/metrics/|ci/signalflag/)")


def ci_target_problem(plugin_py: str, project: str, branch: str):
    """None if plugin.py uploads to `project` / `branch` (what CI on main will do), else what's off."""
    probs = [f"{k} is not {v!r}" for k, v in (("PROJECT", project), ("DEFAULT_BRANCH", branch))
             if not re.search(rf'^{k} = "{re.escape(v)}"\s*$', plugin_py, re.M)]
    return "; ".join(probs) or None


def ci_problem(out: str, branch: str):
    """None if this CI run uploaded to `branch`, else what went wrong.

    pytest exits 1 for the planner fixture by design (one known failing scenario), so 0 and 1 are both normal."""
    code = re.search(r"\[ci exit (-?\d+)\]\s*$", out)
    if not code or int(code.group(1)) not in (0, 1):
        return f"ci exit {code.group(1) if code else '?'}"
    if "SignalFlag: uploaded" not in out or f"to branch {branch!r}" not in out:
        return "no upload to the run's branch"
    return None


def agents_fault(out: str, changed_files=(), seed_main: bool = False) -> bool:
    """Whether a failed CI upload is the agent's.

    Harness signals always win. Then a visible agent signal decides. Otherwise it is the agent's only if main's change
    (`changed_files`, vs the seed) touched the hook code or the metrics config. On the harness's seed main the repo is
    untouched, so only the server rejecting the config (after the agent changed the branch's server config) counts."""
    if HARNESS_FAIL.search(out):
        return False
    if seed_main:
        return bool(re.search(r"Failed to import config|invalid metrics config|config validation failed", out))
    if AGENT_FAIL.search(out):
        return True
    return any(AGENT_PATHS.match(f) for f in changed_files)

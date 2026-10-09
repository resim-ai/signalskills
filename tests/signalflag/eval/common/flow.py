"""Shared by the runners that ship through git (update-metrics, finish-setup): the agent's GitHub-looking env, reading a
SignalFlag branch, simulated CI from `main` with its target guard and fault attribution, and PR detection / merge.

Runners pass in the onboard base module (`base`, for run_claude) and their own project / upload command."""
import json, os, re, subprocess, tempfile
from pathlib import Path

from common import ci_checks
from common.fake_gh import install_fake_gh, read_prs
from common.git_remote import NotMergeable, add_bare_remote, bare_path, fake_ssh, merge_pr_branch, simulate_ci, ssh_env

MCP = json.dumps({"mcpServers": {"signalflag": {"type": "http", "url": "https://bff.resim.ai/mcp"}}})


def sh(cmd, cwd, env=None, timeout=600):
    ws = Path(cwd)  # in a workspace with the fake ssh, git can't reach any network remote
    guard = ssh_env(ws) if fake_ssh(ws).exists() else {}
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **guard, **(env or {})})


# ---------------------------------------------------------------- the agent's GitHub
def gh_paths(ws):
    return ws.parent / (ws.name + ".bin"), ws.parent / (ws.name + ".gh.jsonl")


def install_github(ws, gh_mode="ok"):
    """origin = a local bare repo that reads as GitHub (main pushed); a recording fake `gh`."""
    add_bare_remote(ws)
    bin_dir, gh_log = gh_paths(ws)
    gh_log.unlink(missing_ok=True)
    install_fake_gh(bin_dir, gh_log, gh_mode)


def agent_env(ws):
    """The agent's env: the fake gh first on PATH, its log, and git that can't reach any real remote."""
    bin_dir, gh_log = gh_paths(ws)
    return {"PATH": f"{bin_dir.resolve()}:{os.environ['PATH']}", "FAKE_GH_LOG": str(gh_log.resolve()), **ssh_env(ws)}


def agent_args(base, env, model, session, first):
    a = ["--model", model, "--output-format", "stream-json", "--verbose", "--setting-sources", "project,local",
         "--plugin-dir", str(base.plugin_dir()), "--strict-mcp-config", "--mcp-config", MCP,
         "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "TodoWrite", "mcp__signalflag",
         "--disallowedTools", "AskUserQuestion", "WebFetch", "WebSearch", "Agent", "Task",
         "mcp__signalflag__draft_launch_batch", "mcp__signalflag__draft_archive", "mcp__signalflag__draft_delete",
         "mcp__signalflag__upsert_project"]
    if env:
        a += ["--settings", json.dumps({"env": env})]
    return a + (["--session-id", session] if first else ["--resume", session])


# ---------------------------------------------------------------- the server
def server_state(base, project_id, branch):
    """Read the branch's server config through the MCP (read-only side call)."""
    schema = {"type": "object", "additionalProperties": False,
              "required": ["metric_names", "set_members", "version_count"],
              "properties": {"metric_names": {"type": "array", "items": {"type": "string"}},
                             "set_members": {"type": "object", "additionalProperties": {"type": "array",
                                                                                       "items": {"type": "string"}}},
                             "version_count": {"type": "integer"}}}
    prompt = (f"Using only SignalFlag MCP read tools: find branch '{branch}' in project {project_id} (list_branches with "
              "name filter), call get_metrics_config with include_content true, and report every metric name defined "
              "under `metrics:`, each metrics set's members, and how many config versions exist.")
    for attempt in range(2):  # an empty read is the harness's problem, never scored as the agent's
        with tempfile.TemporaryDirectory() as d:
            _, res = base.run_claude(["--model", "claude-sonnet-5-5", "--output-format", "json", "--setting-sources",
                                      "local", "--strict-mcp-config", "--mcp-config", MCP, "--allowedTools",
                                      "mcp__signalflag__list_branches", "mcp__signalflag__get_metrics_config",
                                      "--json-schema", json.dumps(schema), "--no-session-persistence"], prompt, d, 300)
        out = res.get("structured_output") or {}
        if out.get("metric_names"):
            return out
    raise RuntimeError(f"harness: server_state read for {branch!r} came back empty twice: {str(res.get('result'))[:300]}")


def branch_exists(project_id, branch):
    """Whether the SignalFlag branch exists at all (SDK REST call, exact name)."""
    from signalflag.sdk.auth import DeviceCodeClient
    from signalflag.sdk.client.api.projects import list_branches_for_project
    r = list_branches_for_project.sync(client=DeviceCodeClient(), project_id=project_id, name=branch, page_size=100)
    if r is None or not hasattr(r, "branches"):
        raise RuntimeError(f"harness: list_branches for {branch!r} failed: {r!r}")
    return any(b.name == branch for b in r.branches or [])


# ---------------------------------------------------------------- CI and the merge
def mark_pushed_main(ws, state):
    """Records whether the agent moved origin/main off the harness's seed commit. Returns the seed sha."""
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
    seed = git("rev-list", "--max-parents=0", "main").stdout.split()[-1]  # the harness's single seed commit
    remote_main = subprocess.run(["git", f"--git-dir={bare_path(ws)}", "rev-parse", "main"], capture_output=True,
                                 text=True).stdout.strip()
    state["agent_pushed_main"] = bool(remote_main) and remote_main != seed
    return seed


def run_ci(ws, project, branch, upload, state, key, save, seed, seed_main=False, plugin_required=True):
    """One CI run from origin/main, if main still uploads to this run's branch. Returns True if it uploaded.

    plugin_required=False: main without sf_pytest/plugin.py (nothing to upload yet, or the agent left it out of the PR)
    is recorded and skipped, not a harness error."""
    git = lambda *a: subprocess.run(["git", f"--git-dir={bare_path(ws)}", *a], capture_output=True, text=True)
    plugin = git("show", "main:sf_pytest/plugin.py")
    if plugin.returncode:
        if not plugin_required:
            state[key] = "[skipped: main has no sf_pytest/plugin.py]"
            return False
        save(); raise RuntimeError(f"harness: can't read plugin.py on origin/main: {plugin.stderr[-300:]}")
    tampered = ci_checks.ci_target_problem(plugin.stdout, project, branch)
    if tampered:  # never upload anywhere but this run's branch; the agent changed where main uploads
        state["ci_target_tampered"] = tampered
        state[key] = f"[skipped: main's plugin.py upload target changed: {tampered}]"
        return False
    out = simulate_ci(ws, upload, {})
    state[key] = out[-1500:]
    prob = ci_checks.ci_problem(out, branch)
    state[key + "_ok"] = prob is None
    changed = git("diff", "--name-only", seed, "main").stdout.split()  # main's change vs the harness seed
    if prob and not ci_checks.agents_fault(out, changed, seed_main):
        save(); raise RuntimeError(f"harness: {key}: {prob}: {out[-600:]}")
    return prob is None


def find_pr_head(ws, case, gh_log, state, save):
    """Records the PRs and pushed branches; returns the branch to merge, or None (pushed to main, or nothing to merge)."""
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
    prs = read_prs(gh_log)
    state["prs"] = prs
    if git("fetch", "-q", "--prune", "origin").returncode:
        save(); raise RuntimeError("harness: git fetch origin failed")
    remote = [r.split("/", 1)[1] for r in git("for-each-ref", "--sort=-committerdate", "--format=%(refname:short)",
                                             "refs/remotes/origin").stdout.split() if r not in ("origin/main", "origin/HEAD", "origin")]
    state["remote_branches"] = remote
    if state["agent_pushed_main"]:
        return None  # the change went to main without review: nothing to merge
    if prs:
        return prs[-1]["head"].split(":")[-1]
    if case.get("gh", "ok") != "ok" and remote:  # no gh: the user opens the PR by hand from the pushed branch
        return remote[0]
    return None


def merge(ws, head, state, save):
    """Records the head and its files vs main, then merges it in the remote. False if the merge is the agent's failure."""
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
    state["merged_head"] = head
    state["pr_files"] = git("diff", "--name-only", f"origin/main...origin/{head}").stdout.split()
    try:
        merge_pr_branch(ws, head)
    except NotMergeable as e:  # branch never pushed, or a conflict: the agent's outcome
        state["merge_error"] = str(e)
        return False
    except subprocess.CalledProcessError as e:  # clone / push / fetch in the harness
        save(); raise RuntimeError(f"harness: merge of {head!r} failed: {(e.stderr or '')[-400:]}")
    return True


# ---------------------------------------------------------------- the PR
def pr_chat_text(trace):
    """The agent's last chat message that reads as a ready PR: mentions a PR / pull request and has a title line
    (`Title: ...`, a standalone **bold** line or a markdown heading)."""
    for m in reversed([t["content"] for t in trace if t["role"] == "assistant"]):
        if re.search(r"\b(PR|pull request)\b", m, re.I) and re.search(
                r"(?im)^[\s>*_`#-]*title[\s*_`]*:[\s*_`]*\S|^\s*(\*\*[^*\n]{10,}\*\*|#{1,3} \S.{9,})\s*$", m):
            return m
    return ""


def pr_opened(case, st, trace):
    """(opened, body): a PR against main with gh; with no usable gh, the pushed branch plus a ready PR text in chat.
    Never when the agent pushed to main."""
    prs = st.get("prs") or []
    if case.get("gh", "ok") == "ok":
        opened = int(bool(prs) and prs[-1].get("base", "main") == "main")
        body = prs[-1].get("body", "") if prs else ""
    else:
        body = pr_chat_text(trace)
        opened = int(bool(st.get("remote_branches")) and bool(body))
    return opened & int(not st.get("agent_pushed_main")), body

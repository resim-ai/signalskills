"""Eval runner for metric changes on an already-integrated repo (the signalflag-update-metrics flow).

Reuses the onboard runner's conversation loop, persona, judge plumbing, resume, errors sidecar and harness gate.
Each (case, rep) gets the planner repo (fixture planner_integrated) pointed at the scratch project, its own
SignalFlag branch seeded with two real uploads from the repo, and optionally a server-only metric. The agent has the
real SignalFlag MCP (the authenticated server named `signalflag`) and the SDK token in ~/.resim.

Each run also has a local "GitHub": a bare `origin` remote, a fake `gh` first on the agent's PATH that records PRs
(case `gh`: ok | absent | unauthenticated), and, after the conversation, nightly CI simulated as an upload from a
clean checkout of `main`: once before the PR merges, then the PR is merged in the remote and CI runs again. CI uploads
to the run's own branch (plugin.py's DEFAULT_BRANCH, rewritten in make_workspace and committed on main).

  python run_update_metrics_eval.py --variant <v> [--cases a,b] [--reps 2] [--concurrency 3]
  python run_update_metrics_eval.py --approve-harness      # the user's to run
"""
import json, os, re, shutil, subprocess, sys, tempfile, threading, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "onboard"))
sys.path.insert(0, str(HERE.parent))
import run_eval as base  # noqa: E402
from common.fake_gh import install_fake_gh, read_prs  # noqa: E402
from common.git_remote import NotMergeable, add_bare_remote, bare_path, merge_pr_branch, simulate_ci  # noqa: E402

PROJECT = os.environ.get("SF_EVAL_PROJECT", "karthik-test")
PROJECT_ID = os.environ.get("SF_EVAL_PROJECT_ID", "f0fdd355-c8c7-4ff9-a789-05c5cc565c91")
BRANCH_PREFIX = "skilltest-um"
FIXTURE = base.SKT / "fixtures" / "planner_integrated"
PY = str(base.SKT / ".venv" / "bin" / "python")
MCP = json.dumps({"mcpServers": {"signalflag": {"type": "http", "url": "https://bff.resim.ai/mcp"}}})
SERVER_ONLY_METRIC = "Teammate Detour Chart"

base.HERE = HERE
base.FLOW = base.REPO / ".claude" / "hillclimb" / "update-metrics"
base.HARNESS_FILES = [HERE / f for f in ("run_update_metrics_eval.py", "persona_prompt.md", "judge_prompt.md",
                                         "cases.yaml")] + [HERE.parent / "onboard" / "run_eval.py"] + \
                   [HERE.parent / "common" / f for f in ("git_remote.py", "fake_gh.py")]
base.JUDGE_CRITERIA = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "checked_on_real_data",
                       "review_path", "brief_updated", "drift_handling", "process", "pr_ready", "ci_survives"]
base.CRITICAL = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "review_path",
                 "drift_handling", "pr_ready", "ci_survives"]
base.CHECKS = ["repo_has_metric", "additive", "git_review_branch", "no_server_only", "drift_kept", "brief_mentions",
               "suite_runs", "pr_opened", "merged_ci_has_change", "pr_body_drift_note"]
DRIFT_NOTE = re.compile(r"get_metrics_config|server config|drift|server-only", re.I)  # "check the server before merging"
UPLOAD = f"SIGNALFLAG_UPLOAD=1 {PY} -m pytest -q -p no:cacheprovider"  # what CI runs on a clean checkout of main
_PREFIX = ("Work only inside {ws}. This repo uploads to SignalFlag project `" + PROJECT + "`, branch `{branch}` "
           "(see docs/signalflag/). You're signed in (SDK and the SignalFlag MCP). Use only that branch and new "
           "branches whose names start with `" + BRANCH_PREFIX + "-`. I'm the user; I'll answer your messages.\n\n")


class _Prefix(str):
    """base.converse calls PREFIX.format(ws=, home=); the branch is the one make_workspace made for this workspace."""
    def format(self, ws, home=None):
        return _PREFIX.format(ws=ws, branch=_branch[Path(ws).name])


def branch_for(name):
    """A fresh SignalFlag branch per workspace: a rerun must not inherit a previous run's (additive-only) topics."""
    return f"{BRANCH_PREFIX}-{name[:76]}-{uuid.uuid4().hex[:6]}"


base.PREFIX = _Prefix("")

_cases, _branch = {}, {}
_tl = threading.local()  # per-run agent env (PATH with the fake gh, FAKE_GH_LOG); converse runs in run_one's thread


def gh_paths(ws):
    return ws.parent / (ws.name + ".bin"), ws.parent / (ws.name + ".gh.jsonl")


def sh(cmd, cwd, env=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def cfg_rel(case):
    return "ci/signalflag/metrics.yml" if case.get("config_moved") else ".resim/metrics/config.resim.yml"


def make_workspace(case, name):
    ws = base.WORK / name
    for d in (ws, base.WORK / (name + ".home"), base.WORK / (name + ".bin")):
        if d.exists():
            shutil.rmtree(d)
    shutil.copytree(FIXTURE, ws)
    branch = branch_for(name)
    _branch[name] = branch
    sh(f"sed -i 's/^PROJECT = .*/PROJECT = \"{PROJECT}\"/; s/^DEFAULT_BRANCH = .*/DEFAULT_BRANCH = \"{branch}\"/' "
       "sf_pytest/plugin.py", ws)
    if ci_target_problem((ws / "sf_pytest" / "plugin.py").read_text(), branch):
        raise RuntimeError(f"harness: plugin.py target rewrite did not apply: {ci_target_problem((ws / 'sf_pytest' / 'plugin.py').read_text(), branch)}")
    for b in (ws / "docs" / "signalflag").glob("*.md"):
        t = b.read_text()
        t = re.sub(r"- Project: `[^`]*`[^\n]*", f"- Project: `{PROJECT}` (confirmed by user: yes)", t)
        t = re.sub(r"- Branch: `[^`]*`[^\n]*", f"- Branch: `{branch}` (confirmed by user: yes)", t)
        b.write_text(t)
    if case.get("config_moved"):  # the upload syncs ci/signalflag/metrics.yml; a stale copy stays at .resim/
        old = ws / ".resim/metrics/config.resim.yml"
        (ws / "ci/signalflag").mkdir(parents=True)
        shutil.copy(old, ws / "ci/signalflag/metrics.yml")
        shutil.copytree(ws / ".resim/metrics/templates", ws / "ci/signalflag/templates")
        stale = old.read_text().replace(", Scenarios Passed]", "]")
        stale = re.sub(r"  Scenarios Passed:\n(    .*\n)+", "", stale)
        old.write_text(stale)
        p = ws / "sf_pytest/plugin.py"
        p.write_text(p.read_text().replace('CFG = ROOT / ".resim" / "metrics"', 'CFG = ROOT / "ci" / "signalflag"')
                     .replace('str(CFG / "config.resim.yml")', 'str(CFG / "metrics.yml")'))
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("init", "-q", "-b", "main"); git("add", "-A")
    git("-c", "user.name=eval", "-c", "user.email=eval@example.com", "commit", "-qm", "planner + signalflag hook")
    for _ in range(2):  # seed: two real batches from the repo (its config syncs on each)
        r = sh(f"SIGNALFLAG_UPLOAD=1 {PY} -m pytest -q -p no:cacheprovider", ws)
        if "SignalFlag: uploaded" not in r.stdout:
            raise RuntimeError(f"seed upload failed: {(r.stdout + r.stderr)[-800:]}")
    sh("git clean -fdxq -e .venv-signalflag && git checkout -q .", ws)
    if case.get("server_only"):  # a teammate's metric published only on the server
        cfg = (ws / cfg_rel(case)).read_text()
        extra = (f"  {SERVER_ONLY_METRIC}:\n    type: batch\n    description: Detour ratio per scenario (added in the "
                 "web app).\n    query_string: SELECT experience_name AS \"Scenario\", detour_ratio AS \"Ratio\" FROM "
                 "planner_result\n    template_type: system\n    template: bar\n    skip_if_no_data: false\n\n"
                 "  # ---- dashboard ----")
        cfg = cfg.replace("  # ---- dashboard ----", extra, 1).replace(
            "    metrics: [Scenario Map,", f"    metrics: [{SERVER_ONLY_METRIC}, Scenario Map,", 1)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.resim.yml"; p.write_text(cfg)
            r = sh(f"{PY} -c \"from signalflag.sdk.auth import DeviceCodeClient; from signalflag.sdk.bff_client import "
                   f"metrics; metrics.sync_config(DeviceCodeClient(), '{PROJECT_ID}', '{branch}', config_path='{p}', "
                   f"templates_path='{ws}/{Path(cfg_rel(case)).parent}/templates')\"", ws)
            if r.returncode:
                raise RuntimeError(f"server-only plant failed: {r.stderr[-600:]}")
    add_bare_remote(ws)  # origin = a local bare repo standing in for GitHub; main pushed
    bin_dir, gh_log = gh_paths(ws)
    gh_log.unlink(missing_ok=True)
    install_fake_gh(bin_dir, gh_log, case.get("gh", "ok"))
    if case.get("dirty_tree"):  # an unrelated, uncommitted edit the user doesn't want in the PR
        with open(ws / "planner" / "plan.py", "a") as f:
            f.write("# wip\n")
    return ws


def agent_args(model, session, first):
    a = ["--model", model, "--output-format", "stream-json", "--verbose", "--setting-sources", "project,local",
         "--plugin-dir", str(base.plugin_dir()), "--strict-mcp-config", "--mcp-config", MCP,
         "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "TodoWrite", "mcp__signalflag",
         "--disallowedTools", "AskUserQuestion", "WebFetch", "WebSearch", "Agent", "Task",
         "mcp__signalflag__draft_launch_batch", "mcp__signalflag__draft_archive", "mcp__signalflag__draft_delete",
         "mcp__signalflag__upsert_project"]
    env = getattr(_tl, "env", None)
    if env:
        a += ["--settings", json.dumps({"env": env})]
    return a + (["--session-id", session] if first else ["--resume", session])


def server_state(branch):
    """Read the branch's server config through the MCP (read-only side call)."""
    schema = {"type": "object", "additionalProperties": False,
              "required": ["metric_names", "set_members", "version_count"],
              "properties": {"metric_names": {"type": "array", "items": {"type": "string"}},
                             "set_members": {"type": "object", "additionalProperties": {"type": "array",
                                                                                       "items": {"type": "string"}}},
                             "version_count": {"type": "integer"}}}
    prompt = (f"Using only SignalFlag MCP read tools: find branch '{branch}' in project {PROJECT_ID} (list_branches with "
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


def review_ref(ws, case):
    """The review branch to grade when the agent finished back on main with a clean config (e.g. to hand the user
    their unrelated work-in-progress back): the newest local branch ahead of main. None: grade the working tree."""
    if sh("git rev-parse --abbrev-ref HEAD", ws).stdout.strip() != "main" or \
            sh(f"git status --porcelain -- {cfg_rel(case)} docs/signalflag", ws).stdout.strip():
        return None
    for b in sh("git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/heads", ws).stdout.split():
        if b != "main" and int(sh(f"git rev-list --count main..{b}", ws).stdout.strip() or 0):
            return b
    return None


def repo_state(ws, case):
    ref = review_ref(ws, case)
    with tempfile.TemporaryDirectory() as td:
        src = ws
        if ref:  # read the branch's tree without touching the user's checkout
            src = Path(td) / "review"
            sh(f"git worktree add -q --detach {src} {ref}", ws)
        cfg_path = src / cfg_rel(case)
        cfg = base.yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        briefs = {p.name: p.read_text() for p in (src / "docs" / "signalflag").glob("*.md")}
        r = sh(f"{PY} -m pytest -q -p no:cacheprovider", src, timeout=300)
        if ref:
            sh(f"git worktree remove --force {src}", ws)
    log = sh("git log --all --oneline --decorate", ws).stdout
    branches = sh("git branch --format='%(refname:short)'", ws).stdout.split()
    review_commits = max([int(sh(f"git rev-list --count main..{b}", ws).stdout.strip() or 0)
                          for b in branches if b != "main"] or [0])
    main_log = sh("git log main --oneline", ws).stdout.strip().splitlines()
    diff = sh("git diff main --stat; git diff --stat; git status --short", ws).stdout
    code_diff = sh("git diff main -- sf_pytest tests conftest.py planner; git diff -- sf_pytest tests conftest.py "
                   "planner", ws).stdout
    if ref:
        diff = f"(graded branch {ref}; the checkout is back on main)\n" + sh(f"git diff main...{ref} --stat", ws).stdout + diff
        code_diff = sh(f"git diff main...{ref} -- sf_pytest tests conftest.py planner", ws).stdout + code_diff
    suite = (r.stdout.strip().splitlines() or [""])[-1]
    return {"cfg": cfg, "log": log, "branches": branches, "main_commits": len(main_log), "review_branch_commits": review_commits, "diff": diff,
            "code_diff": code_diff[:6000], "briefs": briefs, "suite": suite, "graded_ref": ref or "working tree"}


def metric_names(cfg):
    return set((cfg or {}).get("metrics", {}) or {})


def pr_chat_text(trace):
    """The agent's last chat message that reads as a ready PR: mentions a PR / pull request and has a title line
    (`Title: ...`, a standalone **bold** line or a markdown heading)."""
    for m in reversed([t["content"] for t in trace if t["role"] == "assistant"]):
        if re.search(r"\b(PR|pull request)\b", m, re.I) and re.search(
                r"(?im)^[\s>*_`#-]*title[\s*_`]*:[\s*_`]*\S|^\s*(\*\*[^*\n]{10,}\*\*|#{1,3} \S.{9,})\s*$", m):
            return m
    return ""


def checks(case, trace, before, after):
    st = after["__state__"]; orig = before["__orig_cfg__"]; cfg = st["repo"]["cfg"]
    new = metric_names(cfg) - metric_names(orig)
    want = {"um-metric-only": "clearance_margin", "um-drift": "ratio_margin", "um-pressure-server-only":
            "clearance_margin", "um-config-moved": "clearance_margin", "um-dirty-tree": "clearance_margin",
            "um-no-gh": "clearance_margin"}.get(case["id"])
    if want:
        has = any(want in str(cfg["metrics"][m].get("query_string", "")) for m in new)
    else:  # emission: a new column/topic about planning time, used by a new metric
        topics_new = {f"{t}.{c}" for t, v in (cfg.get("topics") or {}).items() for c in (v.get("schema") or {})} - \
                     {f"{t}.{c}" for t, v in (orig.get("topics") or {}).items() for c in (v.get("schema") or {})}
        cols = [tc.split(".")[1] for tc in topics_new if re.search(r"time|ms|dur|latency|elapsed", tc, re.I)]
        has = bool(cols) and any(any(c in str(cfg["metrics"][m].get("query_string", "")) for c in cols) for m in new)
    additive = all(t in (cfg.get("topics") or {}) and all(
        (cfg["topics"][t].get("schema") or {}).get(c) == ty for c, ty in (v.get("schema") or {}).items())
        for t, v in (orig.get("topics") or {}).items())
    pushed_main = bool(st.get("agent_pushed_main"))  # the review path was skipped: no PR, no review branch credit
    review = st["repo"]["main_commits"] == 1 and st["repo"]["review_branch_commits"] > 0 and not pushed_main
    server = st["server"]
    server_only = set(server.get("metric_names") or []) - metric_names(cfg)
    prs = st.get("prs") or []
    pr_text = pr_chat_text(trace)
    if case.get("gh", "ok") == "ok":
        pr_opened = int(bool(prs) and prs[-1].get("base", "main") == "main")
        pr_body = prs[-1].get("body", "") if prs else ""
    else:  # no usable gh: the review branch is on origin and the PR's title and body are in the chat
        pr_opened = int(bool(st.get("remote_branches")) and bool(pr_text))
        pr_body = pr_text
    pr_opened &= int(not pushed_main)
    after_merge = set((st.get("server_after_merge_and_ci") or {}).get("metric_names") or [])
    merged_ci = int(bool(new) and new <= after_merge and not pushed_main and not st.get("ci_target_tampered"))
    if case.get("server_only"):
        merged_ci &= int(SERVER_ONLY_METRIC in after_merge)
    c = {"repo_has_metric": int(has), "additive": int(additive), "git_review_branch": int(review),
         "pr_opened": pr_opened, "merged_ci_has_change": merged_ci,
         "pr_body_drift_note": int(bool(DRIFT_NOTE.search(pr_body))),
         "no_server_only": int(not server_only) if server else None,
         "drift_kept": (int(SERVER_ONLY_METRIC in metric_names(cfg)) if case.get("server_only") else None),
         "brief_mentions": int(any(m in t for m in new for t in st["repo"]["briefs"].values())) if new else 0,
         "suite_runs": int("3 passed" in st["repo"]["suite"] and "1 failed" in st["repo"]["suite"])}
    info = {"server_versions_added": (server.get("version_count") or 0) - (2 if case.get("server_only") else 1),
            "new_metrics": sorted(new), "server_only": sorted(server_only), "suite": st["repo"]["suite"],
            "tool_calls": sum(1 for t in trace if t["role"] == "tool_call"),
            "prs": [{k: p.get(k) for k in ("number", "head", "base", "title")} for p in prs],
            "merged_head": st.get("merged_head"), "pr_files": st.get("pr_files"),
            "pr_has_plan_py": int("planner/plan.py" in (st.get("pr_files") or [])) if st.get("merged_head") else None,
            "server_after_merge_and_ci": sorted(after_merge),
            "mcp_writes": [t["name"] for t in trace if t["role"] == "tool_call" and re.search(
                r"push_metrics_config|save_metric_instance", t["name"] or "")]}
    return c, info, []


def judge(case, trace, before, after, ws_files, judge_model):
    st = after["__state__"]
    state = {"repo_metric_names_before": sorted(metric_names(before["__orig_cfg__"])),
             "repo_metric_names_after": sorted(metric_names(st["repo"]["cfg"])),
             "repo_sets_after": (st["repo"]["cfg"] or {}).get("metrics sets"),
             "git_log_all_branches": st["repo"]["log"], "git_diff_vs_main_and_worktree": st["repo"]["diff"],
             "emit_code_diff": st["repo"]["code_diff"], "local_suite": st["repo"]["suite"],
             "server_branch_config": st["server"], "briefs_after": st["repo"]["briefs"],
             "server_versions_added_during_run": (st["server"].get("version_count") or 0) - (2 if case.get("server_only") else 1),
             "gh_mode": case.get("gh", "ok"), "prs_opened_with_gh": st.get("prs"),
             "remote_branches_after_run": st.get("remote_branches"),
             "merged_head": st.get("merged_head"), "files_changed_by_merged_branch": st.get("pr_files"),
             "merge_error": st.get("merge_error"),
             "server_branch_config_after_ci_before_merge": st.get("server_after_ci_before_merge"),
             "ci_before_merge_output_tail": st.get("ci_before_merge"),
             "server_branch_config_after_merge_and_ci": st.get("server_after_merge_and_ci"),
             "ci_after_merge_output_tail": st.get("ci_after_merge"), "ci_after_merge_uploaded": st.get("ci_after_merge_ok"),
             "agent_pushed_to_remote_main": st.get("agent_pushed_main"),
             "ci_target_tampered": st.get("ci_target_tampered")}
    state["briefs_after"] = state.pop("briefs_after")  # longest field last, so truncation never hides the CI results
    prompt = (HERE / "judge_prompt.md").read_text()
    for k, v in {"{expect}": base.yaml.safe_dump(case["expect"], sort_keys=False), "{persona}": case["persona"],
                 "{state}": json.dumps(state, indent=1)[:40000], "{transcript}": base.condensed(trace)}.items():
        prompt = prompt.replace(k, v)
    crit = {"type": "object", "additionalProperties": False, "required": ["verdict", "why"],
            "properties": {"verdict": {"type": "string", "enum": ["pass", "fail", "na"]}, "why": {"type": "string"}}}
    schema = {"type": "object", "additionalProperties": False, "required": base.JUDGE_CRITERIA + ["overall", "top_issue"],
              "properties": {**{k: crit for k in base.JUDGE_CRITERIA}, "overall": {"type": "number"},
                             "top_issue": {"type": "string"}}}
    return base.side_call(judge_model, "You are a strict, fair grader of agent transcripts. Output only the requested "
                          "JSON.", prompt, schema, timeout=600, effort="high")


def ci_target_problem(plugin_py, branch):
    """None if plugin.py uploads to karthik-test and this run's branch (what CI on main will do), else what's off."""
    probs = [f"{k} is not {v!r}" for k, v in (("PROJECT", PROJECT), ("DEFAULT_BRANCH", branch))
             if not re.search(rf'^{k} = "{re.escape(v)}"\s*$', plugin_py, re.M)]
    return "; ".join(probs) or None


def ci_problem(out, branch):
    """None if this CI run uploaded to the run's own branch, else what went wrong.

    pytest exits 1 here by design (the planner suite has one known failing scenario), so 0 and 1 are both normal."""
    code = re.search(r"\[ci exit (-?\d+)\]\s*$", out)
    if not code or int(code.group(1)) not in (0, 1):
        return f"ci exit {code.group(1) if code else '?'}"
    if "SignalFlag: uploaded" not in out or f"to branch {branch!r}" not in out:
        return "no upload to the run's branch"
    return None


_HARNESS_FAIL = re.compile(r"no valid login token|ConnectionError|ConnectTimeout|ReadTimeout|Max retries exceeded|"
                           r"timed out|Temporary failure in name resolution|Name or service not known|"
                           r"\b(429|50[0-4])\b|Too Many Requests|rate.?limit|Bad Gateway|Service Unavailable|"
                           r"Internal Server Error|Unauthorized|\b401\b|\b403\b", re.I)
_AGENT_FAIL = re.compile(r"Failed to import config|ERROR collecting|INTERNALERROR.*(sf_pytest|conftest)|"
                         r"(^|[\s\"/])(sf_pytest/\w+\.py|conftest\.py)[\":]|SyntaxError|ImportError|"
                         r"ModuleNotFoundError|yaml\.(scanner|parser)\.", re.M)


def agents_fault(out, seed_main=False):
    """A failed CI upload is the agent's only when its change visibly caused it (its code or config, rejected by
    pytest or the server) and nothing points at the network, the service or the login. On the harness's seed main
    the repo is untouched, so only the server rejecting the upload's config (after the agent changed the branch's
    server config) counts."""
    if _HARNESS_FAIL.search(out):
        return False
    return bool(re.search(r"Failed to import config", out) if seed_main else _AGENT_FAIL.search(out))


def run_ci(ws, branch, state, key, save, seed_main=False):
    """One CI run from origin/main, if main still uploads to this run's branch. Returns True if it uploaded."""
    git = lambda *a: subprocess.run(["git", f"--git-dir={bare_path(ws)}", *a], capture_output=True, text=True)
    plugin = git("show", "main:sf_pytest/plugin.py")
    if plugin.returncode:
        save(); raise RuntimeError(f"harness: can't read plugin.py on origin/main: {plugin.stderr[-300:]}")
    tampered = ci_target_problem(plugin.stdout, branch)
    if tampered:  # never upload anywhere but this run's branch; the agent changed where main uploads
        state["ci_target_tampered"] = tampered
        state[key] = f"[skipped: main's plugin.py upload target changed: {tampered}]"
        return False
    out = simulate_ci(ws, UPLOAD, {})
    state[key] = out[-1500:]
    prob = ci_problem(out, branch)
    state[key + "_ok"] = prob is None
    if prob and not agents_fault(out, seed_main):
        save(); raise RuntimeError(f"harness: {key}: {prob}: {out[-600:]}")
    return prob is None


def ci_and_merge(ws, case, branch, gh_log, state, save):
    """Tonight's CI (PR not merged), then merge the PR in the remote, then the first CI after the merge."""
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
    seed = git("rev-list", "--max-parents=0", "main").stdout.split()[-1]  # the harness's single seed commit
    remote_main = subprocess.run(["git", f"--git-dir={bare_path(ws)}", "rev-parse", "main"], capture_output=True,
                                 text=True).stdout.strip()
    state["agent_pushed_main"] = bool(remote_main) and remote_main != seed
    # On the seed main only a server-side rejection (the agent changed the branch's config) can be the agent's
    run_ci(ws, branch, state, "ci_before_merge", save, seed_main=not state["agent_pushed_main"])
    state["server_after_ci_before_merge"] = server_state(branch)
    prs = read_prs(gh_log)
    state["prs"] = prs
    if git("fetch", "-q", "--prune", "origin").returncode:
        save(); raise RuntimeError("harness: git fetch origin failed")
    remote = [r.split("/", 1)[1] for r in git("for-each-ref", "--sort=-committerdate", "--format=%(refname:short)",
                                             "refs/remotes/origin").stdout.split() if r not in ("origin/main", "origin/HEAD", "origin")]
    state["remote_branches"] = remote
    if state["agent_pushed_main"]:
        return  # the change went to main without review: nothing to merge, merged_ci_has_change is 0
    if prs:
        head = prs[-1]["head"].split(":")[-1]
    elif case.get("gh", "ok") != "ok" and remote:  # no gh: the user opens the PR by hand from the pushed branch
        head = remote[0]
    else:
        return
    state["merged_head"] = head
    state["pr_files"] = git("diff", "--name-only", f"origin/main...origin/{head}").stdout.split()
    try:
        merge_pr_branch(ws, head)
    except NotMergeable as e:  # branch never pushed, or a conflict: the agent's outcome
        state["merge_error"] = str(e)
        return
    except subprocess.CalledProcessError as e:  # clone / push / fetch in the harness
        save(); raise RuntimeError(f"harness: merge of {head!r} failed: {(e.stderr or '')[-400:]}")
    run_ci(ws, branch, state, "ci_after_merge", save)
    state["ci_after_merge_ok"] = state.get("ci_after_merge_ok", False)
    state["server_after_merge_and_ci"] = server_state(branch)


def run_one(case, rep, variant, args):
    vdir = base.FLOW / variant
    name = f"{variant}-{case['id']}-r{rep}"
    if not re.search(r"[Pp]roject:?\s*`", case["persona"]):  # before base.converse injects its onboard default
        case = {**case, "persona": case["persona"].rstrip("\n") + f"\nYour SignalFlag project: `{PROJECT}`; it already exists.\n"}  # matches converse's check
    ws = make_workspace(case, name)
    branch = _branch[name]
    orig = base.yaml.safe_load((ws / cfg_rel(case)).read_text())
    bin_dir, gh_log = gh_paths(ws)
    _tl.env = {"PATH": f"{bin_dir.resolve()}:{os.environ['PATH']}", "FAKE_GH_LOG": str(gh_log.resolve())}
    try:
        trace, meta = base.converse(case, ws, args.model, args.persona_model)
    finally:
        _tl.env = None
        base.clear_session_store(ws)
    state = {"repo": repo_state(ws, case), "server": server_state(branch)}
    before, after = {"__orig_cfg__": orig}, {"__state__": state}
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    (vdir / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=1))
    save = lambda: (vdir / "traces" / f"{case['id']}_rep{rep}.state.json").write_text(
        json.dumps({"before": before, "after": after, "files": "", "ws": str(ws), "branch": branch}, default=str))
    save()
    ci_and_merge(ws, case, branch, gh_log, state, save)
    save()
    grade, expl, info, jres = base.grade_row(case, trace, before, after, "", args.judge_model)
    return base.make_row(case, rep, grade, expl, info, meta, jres, args)


base.checks = checks
base.judge = judge
base.agent_args = agent_args
base.run_one = run_one

if __name__ == "__main__":
    base.main()

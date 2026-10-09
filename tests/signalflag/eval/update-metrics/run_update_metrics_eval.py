"""Eval runner for metric changes on an already-integrated repo (the signalflag-update-metrics flow).

Reuses the onboard runner's conversation loop, persona, judge plumbing, resume, errors sidecar and harness gate.
Each (case, rep) gets the planner repo (fixture planner_integrated) pointed at the scratch project, its own
SignalFlag branch seeded with two real uploads from the repo, and optionally a server-only metric. The agent has the
real SignalFlag MCP (the authenticated server named `signalflag`) and the SDK token in ~/.resim.

  python run_update_metrics_eval.py --variant <v> [--cases a,b] [--reps 2] [--concurrency 3]
  python run_update_metrics_eval.py --approve-harness      # the user's to run
"""
import json, os, re, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "onboard"))
import run_eval as base  # noqa: E402

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
                                         "cases.yaml")] + [HERE.parent / "onboard" / "run_eval.py"]
base.JUDGE_CRITERIA = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "checked_on_real_data",
                       "review_path", "brief_updated", "drift_handling", "process"]
base.CRITICAL = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "review_path",
                 "drift_handling"]
base.CHECKS = ["repo_has_metric", "additive", "git_review_branch", "no_server_only", "drift_kept", "brief_mentions",
               "suite_runs"]
_PREFIX = ("Work only inside {ws}. This repo uploads to SignalFlag project `" + PROJECT + "`, branch `{branch}` "
           "(see docs/signalflag/). You're signed in (SDK and the SignalFlag MCP). Use only that branch and new "
           "branches whose names start with `" + BRANCH_PREFIX + "-`. I'm the user; I'll answer your messages.\n\n")


class _Prefix(str):
    """base.converse calls PREFIX.format(ws=, home=); the branch is derived from the workspace name."""
    def format(self, ws, home=None):
        return _PREFIX.format(ws=ws, branch=branch_for(Path(ws).name))


def branch_for(name):
    return f"{BRANCH_PREFIX}-{name}"[:90]


base.PREFIX = _Prefix("")

_cases, _branch = {}, {}


def sh(cmd, cwd, env=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def cfg_rel(case):
    return "ci/signalflag/metrics.yml" if case.get("config_moved") else ".resim/metrics/config.resim.yml"


def make_workspace(case, name):
    ws = base.WORK / name
    for d in (ws, base.WORK / (name + ".home")):
        if d.exists():
            shutil.rmtree(d)
    shutil.copytree(FIXTURE, ws)
    branch = branch_for(name)
    _branch[name] = branch
    sh(f"sed -i 's/^PROJECT = .*/PROJECT = \"{PROJECT}\"/; s/^DEFAULT_BRANCH = .*/DEFAULT_BRANCH = \"{branch}\"/' "
       "sf_pytest/plugin.py", ws)
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
    return ws


def agent_args(model, session, first):
    a = ["--model", model, "--output-format", "stream-json", "--verbose", "--setting-sources", "project,local",
         "--plugin-dir", str(base.plugin_dir()), "--strict-mcp-config", "--mcp-config", MCP,
         "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "TodoWrite", "mcp__signalflag",
         "--disallowedTools", "AskUserQuestion", "WebFetch", "WebSearch", "Agent", "Task",
         "mcp__signalflag__draft_launch_batch", "mcp__signalflag__draft_archive", "mcp__signalflag__draft_delete",
         "mcp__signalflag__upsert_project"]
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
    with tempfile.TemporaryDirectory() as d:
        _, res = base.run_claude(["--model", "claude-sonnet-5-5", "--output-format", "json", "--setting-sources",
                                  "local", "--strict-mcp-config", "--mcp-config", MCP, "--allowedTools",
                                  "mcp__signalflag__list_branches", "mcp__signalflag__get_metrics_config",
                                  "--json-schema", json.dumps(schema), "--no-session-persistence"], prompt, d, 300)
    return res.get("structured_output") or {}


def repo_state(ws, case):
    cfg_path = ws / cfg_rel(case)
    cfg = base.yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    log = sh("git log --all --oneline --decorate", ws).stdout
    branches = sh("git branch --format='%(refname:short)'", ws).stdout.split()
    review_commits = max([int(sh(f"git rev-list --count main..{b}", ws).stdout.strip() or 0)
                          for b in branches if b != "main"] or [0])
    main_log = sh("git log main --oneline", ws).stdout.strip().splitlines()
    diff = sh("git diff main --stat; git diff --stat; git status --short", ws).stdout
    code_diff = sh("git diff main -- sf_pytest tests conftest.py planner; git diff -- sf_pytest tests conftest.py "
                   "planner", ws).stdout
    briefs = {p.name: p.read_text() for p in (ws / "docs" / "signalflag").glob("*.md")}
    r = sh(f"{PY} -m pytest -q -p no:cacheprovider", ws, timeout=300)
    suite = (r.stdout.strip().splitlines() or [""])[-1]
    return {"cfg": cfg, "log": log, "branches": branches, "main_commits": len(main_log), "review_branch_commits": review_commits, "diff": diff,
            "code_diff": code_diff[:6000], "briefs": briefs, "suite": suite}


def metric_names(cfg):
    return set((cfg or {}).get("metrics", {}) or {})


def checks(case, trace, before, after):
    st = after["__state__"]; orig = before["__orig_cfg__"]; cfg = st["repo"]["cfg"]
    new = metric_names(cfg) - metric_names(orig)
    want = {"um-metric-only": "clearance_margin", "um-drift": "ratio_margin", "um-pressure-server-only":
            "clearance_margin", "um-config-moved": "clearance_margin"}.get(case["id"])
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
    review = st["repo"]["main_commits"] == 1 and st["repo"]["review_branch_commits"] > 0
    server = st["server"]
    server_only = set(server.get("metric_names") or []) - metric_names(cfg)
    c = {"repo_has_metric": int(has), "additive": int(additive), "git_review_branch": int(review),
         "no_server_only": int(not server_only) if server else None,
         "drift_kept": (int(SERVER_ONLY_METRIC in metric_names(cfg)) if case.get("server_only") else None),
         "brief_mentions": int(any(m in t for m in new for t in st["repo"]["briefs"].values())) if new else 0,
         "suite_runs": int("3 passed" in st["repo"]["suite"] and "1 failed" in st["repo"]["suite"])}
    info = {"server_versions_added": (server.get("version_count") or 0) - (2 if case.get("server_only") else 1),
            "new_metrics": sorted(new), "server_only": sorted(server_only), "suite": st["repo"]["suite"],
            "tool_calls": sum(1 for t in trace if t["role"] == "tool_call"),
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
             "server_versions_added_during_run": (st["server"].get("version_count") or 0) - (2 if case.get("server_only") else 1)}
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


def run_one(case, rep, variant, args):
    vdir = base.FLOW / variant
    name = f"{variant}-{case['id']}-r{rep}"
    ws = make_workspace(case, name)
    orig = base.yaml.safe_load((ws / cfg_rel(case)).read_text())
    try:
        trace, meta = base.converse(case, ws, args.model, args.persona_model)
    finally:
        base.clear_session_store(ws)
    state = {"repo": repo_state(ws, case), "server": server_state(_branch[name])}
    before, after = {"__orig_cfg__": orig}, {"__state__": state}
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    (vdir / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=1))
    (vdir / "traces" / f"{case['id']}_rep{rep}.state.json").write_text(
        json.dumps({"before": before, "after": after, "files": "", "ws": str(ws), "branch": _branch[name]}, default=str))
    grade, expl, info, jres = base.grade_row(case, trace, before, after, "", args.judge_model)
    return base.make_row(case, rep, grade, expl, info, meta, jres, args)


base.checks = checks
base.judge = judge
base.agent_args = agent_args
base.run_one = run_one

if __name__ == "__main__":
    base.main()

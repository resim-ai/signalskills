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
from common import ci_checks, flow  # noqa: E402
from common.flow import gh_paths, sh  # noqa: E402

PROJECT = os.environ.get("SF_EVAL_PROJECT", "karthik-test")
PROJECT_ID = os.environ.get("SF_EVAL_PROJECT_ID", "f0fdd355-c8c7-4ff9-a789-05c5cc565c91")
BRANCH_PREFIX = "skilltest-um"
FIXTURE = base.SKT / "fixtures" / "planner_integrated"
PY = str(base.SKT / ".venv" / "bin" / "python")
SERVER_ONLY_METRIC = "Teammate Detour Chart"

base.HERE = HERE
base.FLOW = base.REPO / ".claude" / "hillclimb" / "update-metrics"
base.HARNESS_FILES = [HERE / f for f in ("run_update_metrics_eval.py", "persona_prompt.md", "judge_prompt.md",
                                         "cases.yaml")] + [HERE.parent / "onboard" / "run_eval.py"] + \
                   [HERE.parent / "common" / f for f in ("git_remote.py", "fake_gh.py", "ci_checks.py", "flow.py")]
base.JUDGE_CRITERIA = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "checked_on_real_data",
                       "review_path", "brief_updated", "drift_handling", "process", "pr_ready", "ci_survives"]
base.CRITICAL = ["right_path", "repo_source_of_truth", "server_consistency", "publish_timing", "review_path",
                 "drift_handling", "pr_ready", "ci_survives"]
base.CHECKS = ["repo_has_metric", "additive", "git_review_branch", "no_server_only", "drift_kept", "brief_mentions",
               "suite_runs", "pr_opened", "merged_ci_has_change", "pr_body_drift_note", "pr_touches_owner_only"]
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


def cfg_rel(case):
    return "ci/signalflag/metrics.yml" if case.get("config_moved") else ".resim/metrics/config.resim.yml"


TWO_FILES = (".resim/metrics/planner.yml", ".resim/metrics/shared.yml")  # case two_files: Batch syncs both, merged


def load_cfg(root, case):
    """The repo's metrics config as the SDK sees it: the synced file, or the merge of the two files (case two_files)."""
    paths = [root / f for f in TWO_FILES] if case.get("two_files") else [root / cfg_rel(case)]
    out = {}
    for path in paths:
        if not path.exists():
            continue
        for k, v in (base.yaml.safe_load(path.read_text()) or {}).items():
            out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def split_config(ws):
    """planner.yml: the planner topics and their test/batch metrics and set. shared.yml: the trend charts, set, dashboard."""
    d = ws / ".resim/metrics"
    cfg = base.yaml.safe_load((d / "config.resim.yml").read_text())
    trends = {m for m, v in cfg["metrics"].items() if v.get("type") == "dashboard"}
    sets = cfg["metrics sets"]
    planner = {"version": cfg["version"], "topics": cfg["topics"],
               "metrics": {m: v for m, v in cfg["metrics"].items() if m not in trends},
               "metrics sets": {"Planner Pytest": sets["Planner Pytest"]}}
    shared = {"version": cfg["version"], "metrics": {m: cfg["metrics"][m] for m in cfg["metrics"] if m in trends},
              "metrics sets": {"Planner Pytest Trends": sets["Planner Pytest Trends"]}, "dashboards": cfg["dashboards"]}
    for f, data in (("planner.yml", planner), ("shared.yml", shared)):
        (d / f).write_text(base.yaml.safe_dump(data, sort_keys=False, width=200))
    (d / "config.resim.yml").unlink()
    p = ws / "sf_pytest/plugin.py"
    p.write_text(p.read_text().replace('metrics_config_path=str(CFG / "config.resim.yml")',
                                       'metrics_config_path=[str(CFG / "planner.yml"), str(CFG / "shared.yml")]'))
    for b in (ws / "docs" / "signalflag").glob("*.md"):
        b.write_text(b.read_text().replace(
            "- Path: `.resim/metrics/config.resim.yml`,",
            "- Path: two files, merged on upload: `.resim/metrics/planner.yml` (planner topics, their test and batch "
            "metrics, set `Planner Pytest`) and `.resim/metrics/shared.yml` (trend charts, set `Planner Pytest Trends`, "
            "dashboard),"))


def make_workspace(case, name):
    ws = base.WORK / name
    for d in (ws, base.WORK / (name + ".home"), base.WORK / (name + ".bin")):
        if d.exists():
            shutil.rmtree(d)
    (base.WORK / (name + ".ssh")).unlink(missing_ok=True)
    shutil.copytree(FIXTURE, ws)
    branch = branch_for(name)
    _branch[name] = branch
    sh(f"sed -i 's/^PROJECT = .*/PROJECT = \"{PROJECT}\"/; s/^DEFAULT_BRANCH = .*/DEFAULT_BRANCH = \"{branch}\"/' "
       "sf_pytest/plugin.py", ws)
    prob = ci_checks.ci_target_problem((ws / "sf_pytest" / "plugin.py").read_text(), PROJECT, branch)
    if prob:
        raise RuntimeError(f"harness: plugin.py target rewrite did not apply: {prob}")
    for b in (ws / "docs" / "signalflag").glob("*.md"):
        t = b.read_text()
        t = re.sub(r"- Project: `[^`]*`[^\n]*", f"- Project: `{PROJECT}` (confirmed by user: yes)", t)
        t = re.sub(r"- Branch: `[^`]*`[^\n]*", f"- Branch: `{branch}` (confirmed by user: yes)", t)
        b.write_text(t)
    if case.get("two_files"):
        split_config(ws)
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
    flow.install_github(ws, case.get("gh", "ok"))  # origin = a local bare repo standing in for GitHub; main pushed
    if case.get("dirty_tree"):  # an unrelated, uncommitted edit the user doesn't want in the PR
        with open(ws / "planner" / "plan.py", "a") as f:
            f.write("# wip\n")
    return ws


def agent_args(model, session, first):
    return flow.agent_args(base, getattr(_tl, "env", None), model, session, first)


def server_state(branch):
    return flow.server_state(base, PROJECT_ID, branch)


def review_ref(ws, case):
    """The review branch to grade when the agent finished back on main with a clean config (e.g. to hand the user
    their unrelated work-in-progress back): the newest local branch ahead of main. None: grade the working tree."""
    if sh("git rev-parse --abbrev-ref HEAD", ws).stdout.strip() != "main" or \
            sh(f"git status --porcelain -- .resim ci docs/signalflag", ws).stdout.strip():
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
        cfg = load_cfg(src, case)
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


def checks(case, trace, before, after):
    st = after["__state__"]; orig = before["__orig_cfg__"]; cfg = st["repo"]["cfg"]
    new = metric_names(cfg) - metric_names(orig)
    want = {"um-metric-only": "clearance_margin", "um-drift": "ratio_margin", "um-pressure-server-only":
            "clearance_margin", "um-config-moved": "clearance_margin", "um-dirty-tree": "clearance_margin",
            "um-no-gh": "clearance_margin", "um-two-files": "clearance_margin"}.get(case["id"])
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
    pr_opened, pr_body = flow.pr_opened(case, st, trace)  # no usable gh: pushed branch + PR text in chat
    after_merge = set((st.get("server_after_merge_and_ci") or {}).get("metric_names") or [])
    merged_ci = int(bool(new) and new <= after_merge and not pushed_main and not st.get("ci_target_tampered"))
    if case.get("server_only"):
        merged_ci &= int(SERVER_ONLY_METRIC in after_merge)
    c = {"repo_has_metric": int(has), "additive": int(additive), "git_review_branch": int(review),
         "pr_opened": pr_opened, "merged_ci_has_change": merged_ci,
         "pr_body_drift_note": int(bool(DRIFT_NOTE.search(pr_body))),
         "pr_touches_owner_only": ((lambda f: int(TWO_FILES[0] in f and TWO_FILES[1] not in f))(st.get("pr_files") or [])
                                   if case.get("two_files") else None),
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


def run_ci(ws, branch, state, key, save, seed, seed_main=False):
    return flow.run_ci(ws, PROJECT, branch, UPLOAD, state, key, save, seed, seed_main)


def ci_and_merge(ws, case, branch, gh_log, state, save):
    """Tonight's CI (PR not merged), then merge the PR in the remote, then the first CI after the merge."""
    seed = flow.mark_pushed_main(ws, state)
    # On the seed main only a server-side rejection (the agent changed the branch's config) can be the agent's
    run_ci(ws, branch, state, "ci_before_merge", save, seed, seed_main=not state["agent_pushed_main"])
    state["server_after_ci_before_merge"] = server_state(branch)
    head = flow.find_pr_head(ws, case, gh_log, state, save)  # None: pushed to main (merged_ci_has_change is 0) or no PR
    if head is None or not flow.merge(ws, head, state, save):
        return
    run_ci(ws, branch, state, "ci_after_merge", save, seed)
    state["ci_after_merge_ok"] = state.get("ci_after_merge_ok", False)
    state["server_after_merge_and_ci"] = server_state(branch)


def run_one(case, rep, variant, args):
    vdir = base.FLOW / variant
    name = f"{variant}-{case['id']}-r{rep}"
    if not re.search(r"[Pp]roject:?\s*`", case["persona"]):  # before base.converse injects its onboard default
        case = {**case, "persona": case["persona"].rstrip("\n") + f"\nYour SignalFlag project: `{PROJECT}`; it already exists.\n"}  # matches converse's check
    ws = make_workspace(case, name)
    branch = _branch[name]
    orig = load_cfg(ws, case)
    bin_dir, gh_log = gh_paths(ws)
    _tl.env = flow.agent_env(ws)  # the fake gh first on PATH; the agent's git can't reach any real remote either
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

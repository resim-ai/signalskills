"""One-off: the update-metrics scenario um-metric-only against a real private GitHub repo, end to end.

Unlike run_update_metrics_eval.py (bare local origin, fake gh), the agent here uses the real `gh` and the real origin.
There is no GitHub Actions workflow (CI credentials are ReSim-issued); "CI" is an upload from a fresh clone of the
sandbox's `main` on this machine, the way common.git_remote.simulate_ci does it for the bare remote.

  python run_real_github.py setup      # populate the empty sandbox (planner_integrated -> karthik-test), push main, seed 2 CI uploads
  python run_real_github.py converse   # the agent + persona conversation in a fresh clone (plugin at SF_PLUGIN_REF, default HEAD)
  python run_real_github.py finish     # server state, CI before merge, PR check, gh pr merge, CI after merge, grade

State, trace and grade live in $SF_EVAL_WORK/um-real/ (outside the repo). SignalFlag writes go only to project
karthik-test, branch skilltest-um-real-<yyyymmdd-hhmm>.
"""
import datetime as dt, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

os.environ.setdefault("SF_PLUGIN_REF", "HEAD")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_update_metrics_eval as um  # noqa: E402  (sets up base: plugin dir, MCP agent args, persona loop, judge)

base = um.base
REPO = "resim-ai/signalskills-sandbox-planner"
SSH_URL = f"git@github.com:{REPO}.git"
CASE_ID = "um-metric-only"
OUT = base.WORK / "um-real"
STATE = OUT / "state.json"
README = """# signalskills sandbox: planner

A sandbox repo for testing the signalskills plugin's update-metrics flow end to end against real GitHub.
The planner code and its SignalFlag upload hook are a test fixture, not a product. Uploads go to a scratch
SignalFlag project. Nothing here is customer code or data.
"""


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(st):
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1, default=str))


def run(cmd, cwd=None, check=True, timeout=600, env=None):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    if check and r.returncode:
        raise RuntimeError(f"{cmd!r} failed ({r.returncode}): {(r.stdout + r.stderr)[-800:]}")
    return r


def case():
    c = next(c for c in base.yaml.safe_load((HERE / "cases.yaml").read_text()) if c["id"] == CASE_ID)
    c["persona"] = c["persona"].rstrip("\n") + (f"\nYour SignalFlag project: `{um.PROJECT}`; it already exists. CI "
                                               "uploads to SignalFlag from `main` every night.\n")
    return c


def ci(branch, label, st):
    """One CI run: fresh clone of the sandbox's main, upload with the repo venv. Records the output tail and whether it
    uploaded to `branch`."""
    with tempfile.TemporaryDirectory() as d:
        run(f"git clone -q --branch main {SSH_URL} ci", d)
        ws = Path(d) / "ci"
        sha = run("git rev-parse --short HEAD", ws).stdout.strip()
        prob = um.ci_checks.ci_target_problem((ws / "sf_pytest/plugin.py").read_text(), um.PROJECT, branch)
        if prob:  # never upload anywhere but the run's branch
            raise RuntimeError(f"{label}: main's plugin.py target changed: {prob}")
        r = run(um.UPLOAD, ws, check=False, env={"PYTHONPATH": str(ws)})
    out = r.stdout + r.stderr + f"\n[ci exit {r.returncode}]"
    prob = um.ci_checks.ci_problem(out, branch)
    st.setdefault("ci", {})[label] = {"main_sha": sha, "ok": prob is None, "problem": prob,
                                      "suite": next((l for l in reversed(r.stdout.splitlines()) if " passed" in l
                                                     or " failed" in l), ""), "tail": out[-1200:]}
    save(st)
    print(f"{label}: main {sha} -> {'uploaded' if prob is None else prob}", flush=True)
    if prob:
        raise RuntimeError(f"{label}: {prob}: {out[-600:]}")


def setup():
    st = load()
    if st.get("branch"):
        sys.exit(f"already set up: {st['branch']}")
    info = json.loads(run(f"gh repo view {REPO} --json isEmpty,visibility").stdout)
    if not info["isEmpty"] or info["visibility"] != "PRIVATE":
        sys.exit(f"sandbox is not an empty private repo: {info}")
    branch = "skilltest-um-real-" + dt.datetime.now().strftime("%Y%m%d-%H%M")
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "planner"
        shutil.copytree(um.FIXTURE, ws, ignore=shutil.ignore_patterns("__pycache__", ".venv-signalflag"))
        p = ws / "sf_pytest/plugin.py"
        t = re.sub(r'^PROJECT = .*$', f'PROJECT = "{um.PROJECT}"', p.read_text(), flags=re.M)
        p.write_text(re.sub(r'^DEFAULT_BRANCH = .*$', f'DEFAULT_BRANCH = "{branch}"', t, flags=re.M))
        if um.ci_checks.ci_target_problem(p.read_text(), um.PROJECT, branch):
            raise RuntimeError("plugin.py target rewrite did not apply")
        for b in (ws / "docs/signalflag").glob("*.md"):
            t = re.sub(r"- Project: `[^`]*`[^\n]*", f"- Project: `{um.PROJECT}` (confirmed by user: yes)", b.read_text())
            b.write_text(re.sub(r"- Branch: `[^`]*`[^\n]*", f"- Branch: `{branch}` (confirmed by user: yes)", t))
        (ws / "README.md").write_text(README)
        (ws / ".gitignore").write_text((ws / ".gitignore").read_text() + "__pycache__/\n")
        bad = run(r"grep -rniE 'acme|secret|password|api[_-]?key|BEGIN [A-Z ]*PRIVATE|token\.json\"?\s*:' . || true",
                  ws).stdout
        if bad.strip():
            raise RuntimeError(f"sandbox content check: {bad[:600]}")
        run("git init -q -b main && git add -A && git -c user.name=signalskills-eval -c user.email=eval@example.com "
            f"commit -qm 'planner + signalflag upload hook (sandbox)' && git remote add origin {SSH_URL} && "
            "git push -q -u origin main", ws)
        st = {"branch": branch, "seed_sha": run("git rev-parse HEAD", ws).stdout.strip(),
              "files": run("git ls-files", ws).stdout.split()}
    save(st)
    for i in (1, 2):  # seed: two CI uploads from main
        ci(branch, f"seed_{i}", st)
    st["server_after_seed"] = um.server_state(branch)
    save(st)
    print(json.dumps(st["server_after_seed"]), flush=True)


def converse():
    st = load()
    if not st.get("branch") or st.get("trace_path"):
        sys.exit("run setup first / conversation already done")
    ws = OUT / "agent" / "planner"
    if ws.exists():
        shutil.rmtree(ws)
    ws.parent.mkdir(parents=True)
    run(f"git clone -q {SSH_URL} {ws}")
    um._branch[ws.name] = st["branch"]  # the PREFIX names the run's branch
    c = case()
    st["orig_cfg"] = um.load_cfg(ws, c)
    st["ws"] = str(ws)
    st["plugin_ref"] = run(f"git -C {base.REPO} rev-parse --short {os.environ['SF_PLUGIN_REF']}").stdout.strip()
    save(st)
    try:
        trace, meta = base.converse(c, ws, "claude-opus-5-5", "claude-sonnet-5-5")
    finally:
        base.clear_session_store(ws)
    (OUT / "trace.json").write_text(json.dumps(trace, indent=1))
    st["trace_path"] = str(OUT / "trace.json")
    st["meta"] = {k: meta[k] for k in ("turns", "end_reason", "models", "latency_s", "retries")}
    save(st)
    print(base.condensed(trace), flush=True)


def prs():
    return json.loads(run(f"gh pr list --repo {REPO} --state all --json number,title,body,headRefName,baseRefName,"
                          "state,url,files").stdout)


def finish():
    st = load()
    branch, ws, c = st["branch"], Path(st["ws"]), case()
    trace = json.loads(Path(st["trace_path"]).read_text())
    # 1. the server right after the conversation
    st["server_after_conversation"] = um.server_state(branch)
    st["repo"] = um.repo_state(ws, c)
    remote_main = run(f"git ls-remote {SSH_URL} refs/heads/main").stdout.split()[0]
    st["agent_pushed_main"] = remote_main != st["seed_sha"]
    save(st)
    if st["agent_pushed_main"]:
        sys.exit("the agent moved main on the remote: no review path; record it and stop")
    # 2. tonight's CI, PR not merged
    ci(branch, "ci_before_merge", st)
    st["server_after_ci_before_merge"] = um.server_state(branch)
    save(st)
    # 3. the PR
    open_prs = [p for p in prs() if p["state"] == "OPEN" and p["baseRefName"] == "main"]
    st["prs"] = [{"number": p["number"], "head": p["headRefName"], "base": p["baseRefName"], "title": p["title"],
                  "body": p["body"], "url": p["url"]} for p in open_prs]
    save(st)
    if len(open_prs) != 1:
        sys.exit(f"expected one open PR against main, found {len(open_prs)}")
    pr = open_prs[0]
    st["pr_files"] = [f["path"] for f in pr.get("files") or []]
    st["pr_body_checks"] = {
        "merge_timing": bool(re.search(r"after (this|the PR|it) (is )?merge|once (this|the PR|it) (is )?merged|"
                                       r"next (nightly|CI)|upload from `?main|until (this|the PR|it) merges",
                                       pr["body"], re.I)),
        "drift_check": bool(um.DRIFT_NOTE.search(pr["body"]))}
    save(st)
    # 4. merge (the sandbox exists for this)
    run(f"gh pr merge {pr['number']} --repo {REPO} --merge")
    st["merged_pr"] = pr["number"]; st["merged_head"] = pr["headRefName"]
    save(st)
    # 5. the first CI after the merge
    ci(branch, "ci_after_merge", st)
    st["ci_after_merge_ok"] = st["ci"]["ci_after_merge"]["ok"]
    # 6. the server after merge + CI
    st["server_after_merge_and_ci"] = um.server_state(branch)
    save(st)
    grade(st, c, trace)


def grade(st, c, trace):
    """The update-metrics runner's checks + judge on this run (gh mode ok: the PR is the real one)."""
    state = {**st, "server": st["server_after_conversation"]}
    before, after = {"__orig_cfg__": st["orig_cfg"]}, {"__state__": state}
    g, expl, info, _ = base.grade_row(c, trace, before, after, "", "claude-sonnet-5-5")
    st["grade"] = {"grade": g, "explanation": expl, "info": info}
    save(st)
    print(json.dumps(st["grade"], indent=1, default=str), flush=True)


if __name__ == "__main__":
    {"setup": setup, "converse": converse, "finish": finish,
     "grade": lambda: grade(load(), case(), json.loads(Path(load()["trace_path"]).read_text()))}[sys.argv[1]]()

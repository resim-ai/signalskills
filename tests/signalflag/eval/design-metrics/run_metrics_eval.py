"""Eval runner for signalflag-design-metrics. Reuses the onboard runner (conversation loop, persona, judge
plumbing, resume, errors sidecar, harness gate) with its own cases, starting briefs, checks and rubric.

  python run_metrics_eval.py --variant baseline [--cases a,b] [--reps 2] [--concurrency 4]
  python run_metrics_eval.py --variant baseline --regrade
  python run_metrics_eval.py --approve-harness          # the user records the harness sha
Writes .claude/hillclimb/design-metrics/<variant>/...
"""
import concurrent.futures as cf, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "onboard"))
import run_eval as base  # noqa: E402

base.HERE = HERE
base.FLOW = base.REPO / ".claude" / "hillclimb" / "design-metrics"
base.HARNESS_FILES = [HERE / f for f in ("run_metrics_eval.py", "persona_prompt.md", "judge_prompt.md", "cases.yaml")] + \
    sorted((HERE / "briefs").glob("*.md")) + [HERE.parent / "onboard" / "run_eval.py"]
base.JUDGE_CRITERIA = ["catches_bad_run", "points_to_cause", "audience_fit", "economy", "visual", "levels", "media",
                       "events", "data_and_python", "thresholds", "required_optional", "grounded", "process"]
base.CRITICAL = ["catches_bad_run", "points_to_cause", "audience_fit", "economy", "visual", "media", "events",
                 "thresholds", "grounded"]
base.CHECKS = ["plan_written", "profile_written", "row_budget", "has_charts", "thresholds_sourced", "events_section",
               "no_sdk_before_plan"]
CHART_RE = re.compile(r"line|bar|histogram|state.?timeline|image|video|gif|mp4|custom|plotly|scatter|heatmap|pie|box|xy",
                      re.I)

_make_workspace = base.make_workspace
_cases = {}


def make_workspace(fixture, name):
    ws = _make_workspace(fixture, name)
    case = next(c for cid, c in _cases.items() if re.search(rf"-{re.escape(cid)}-r\d+$", name))
    dst = ws / "docs" / "signalflag" / case["brief_file"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text((HERE / "briefs" / f"{case['id']}.md").read_text())
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("add", "-A")
    git("-c", "user.name=eval", "-c", "user.email=eval@example.com", "commit", "-qm", "approved SignalFlag brief")
    return ws


def section(t, h):
    m = re.search(rf"^##\s+{re.escape(h)}\b(.*?)(?=^##\s|\Z)", t, re.M | re.S)
    return (m.group(1) if m else "").strip()


def plan_rows(plan):
    """Rows of the metric table in the Metrics plan (the first table with Metric and Level columns)."""
    cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
    blocks, cur = [], []
    for l in plan.splitlines():
        if l.strip().startswith("|"):
            cur.append(l)
        elif cur:
            blocks.append(cur); cur = []
    if cur:
        blocks.append(cur)
    for lines in blocks:
        head = [h.lower() for h in cells(lines[0])]
        if len(lines) < 3 or not any("metric" in h for h in head) or not any("level" in h for h in head):
            continue
        rows = []
        for l in lines[2:]:
            c = cells(l)
            if len(c) < 3 or set(l.strip()) <= set("|-: ") or not re.match(r"^\**[\d]", c[0]):
                continue
            d = dict(zip(head, c))
            d["_malformed"] = len(c) != len(head)  # a stray | in a cell shifts columns; don't misread it
            rows.append(d)
        if rows:
            return rows
    return []


def col(row, *names):
    for k, v in row.items():
        if any(n in k for n in names):
            return v
    return ""


def checks(case, trace, before, after):
    brief = next((t for p, t in after.items() if p.endswith(case["brief_file"])), "")
    plan, prof = section(brief, "Metrics plan"), section(brief, "Data profile")
    rows = plan_rows(plan)
    test_rows = [r for r in rows if re.search(r"\btest\b", col(r, "level"), re.I)]
    status = [r for r in rows if not r["_malformed"] and col(r, "status").strip("—-– ").strip()]
    charts = [r for r in rows if CHART_RE.search(col(r, "template"))]
    c = {"plan_written": int(bool(plan) and not plan.startswith("_pending") and len(rows) > 0),
         "profile_written": int(bool(prof) and not prof.startswith("_pending")),
         "row_budget": int(0 < len(test_rows) <= 20 and len(rows) <= 40) if rows else 0,
         "has_charts": int(len(charts) >= (1 if not case["expect"].get("bad_runs") and "none" in case["tags"] else 3)),
         "thresholds_sourced": int(all(col(r, "source").strip("—-– _").strip() for r in status)) if rows else 0,
         "events_section": int(bool(re.search(r"^#+\s*Events", plan, re.M))) if plan else 0}
    plan_at = next((i for i, t in enumerate(trace) if t["role"] == "tool_call" and "Metrics plan" in t["content"]
                    and "docs/signalflag" in t["content"]), len(trace))
    cmds = [(i, json.loads(t["content"]).get("command", "")) for i, t in enumerate(trace)
            if t["role"] == "tool_call" and t["name"] == "Bash"]
    sdk = re.compile(r"\b(pip3?|uv)\b[^;&|\n]*\b(install|add)\b[^;&|\n]*?(?<![/.\w-])signalflag(?![\w/.-])")  # the package, not a venv path
    c["no_sdk_before_plan"] = int(not any(sdk.search(cmd) or base.LOGIN_RE.search(cmd)
                                          for i, cmd in cmds if i < plan_at))
    info = {"test_metrics": len(test_rows), "metrics_total": len(rows), "chart_metrics": len(charts),
            "status_checks": len(status), "malformed_rows": sum(r["_malformed"] for r in rows), "tool_calls": sum(1 for t in trace if t["role"] == "tool_call"),
            "installs_total": sum(1 for _, cmd in cmds if base.INSTALL_RE.search(cmd))}
    return c, info, [brief]


def judge(case, trace, before, after, ws_files, judge_model):
    sk = base.REPO / "skills" / "signalflag-design-metrics"
    brief = next((t for p, t in after.items() if p.endswith(case["brief_file"])), "(no brief)")
    prompt = (HERE / "judge_prompt.md").read_text()
    for k, v in {"{skill}": (sk / "SKILL.md").read_text(), "{catalog}": (sk / "catalog.md").read_text(),
                 "{persona}": case["persona"].strip(), "{expect}": base.yaml.safe_dump(case["expect"], sort_keys=False),
                 "{files}": ws_files, "{transcript}": base.condensed(trace), "{brief}": brief}.items():
        prompt = prompt.replace(k, v)
    crit = {"type": "object", "additionalProperties": False, "required": ["verdict", "why"],
            "properties": {"verdict": {"type": "string", "enum": ["pass", "fail", "na"]}, "why": {"type": "string"}}}
    schema = {"type": "object", "additionalProperties": False, "required": base.JUDGE_CRITERIA + ["overall", "top_issue"],
              "properties": {**{k: crit for k in base.JUDGE_CRITERIA}, "overall": {"type": "number"},
                             "top_issue": {"type": "string"}}}
    return base.side_call(judge_model, "You are a strict, fair grader of metrics designs for robotics test results. "
                          "Output only the requested JSON.", prompt, schema, timeout=600, effort="high")


_snap = None


def plugin_dir_from_ref():
    """SF_PLUGIN_REF=<git ref>: run the plugin as it was at that ref (e.g. HEAD before this work) instead of the tree."""
    global _snap
    import os, tempfile
    ref = os.environ.get("SF_PLUGIN_REF")
    if not ref:
        return _orig_plugin_dir()
    with base._lock:
        if _snap is None:
            d = Path(tempfile.mkdtemp(prefix="sf-plugin-ref-")) / "signalskills"
            d.mkdir(parents=True)
            arc = subprocess.run(["git", "-C", str(base.REPO), "archive", ref, ".claude-plugin", "skills", ".mcp.json"],
                                 check=True, capture_output=True).stdout
            subprocess.run(["tar", "-x", "-C", str(d)], input=arc, check=True)
            _snap = d
    return _snap


_orig_plugin_dir = base.plugin_dir
base.plugin_dir = plugin_dir_from_ref
base.make_workspace = make_workspace
base.checks = checks
base.judge = judge

if __name__ == "__main__":
    for c in base.yaml.safe_load((HERE / "cases.yaml").read_text()):
        _cases[c["id"]] = c
    base.main()

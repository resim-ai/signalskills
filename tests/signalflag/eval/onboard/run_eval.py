"""Eval runner for the signalflag-onboard skill.

Each (case, rep): fresh git workspace from a fixture, then a multi-turn conversation between the agent
under test (`claude -p` with this repo as the only plugin) and a simulated user (persona model), then
programmatic checks on the workspace + transcript and a rubric judge. Writes the hillclimb layout:

  .claude/hillclimb/onboard/<variant>/results.jsonl   one row per (case, rep), appended as each finishes
  .claude/hillclimb/onboard/<variant>/traces/<id>_rep<k>.json
  .claude/hillclimb/onboard/<variant>/errors.jsonl     harness failures (never in results.jsonl)

  python run_eval.py --variant baseline [--cases a,b] [--reps 2] [--concurrency 4]
  python run_eval.py --variant baseline --regrade      # re-run checks + judge on stored transcripts
  python run_eval.py --approve-harness                 # the user records the harness sha
"""
import argparse, concurrent.futures as cf, datetime as dt, glob, hashlib, json, os, random, re, shutil
import subprocess, sys, tempfile, threading, time, uuid
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SKT = REPO / "tests" / "signalflag"
FLOW = REPO / ".claude" / "hillclimb" / "onboard"
WORK = Path(os.environ.get("SF_EVAL_WORK", Path.home() / "sf-eval-work"))  # outside the repo on purpose
CLAUDE = shutil.which("claude") or "claude"
HARNESS_FILES = [HERE / f for f in ("run_eval.py", "persona_prompt.md", "judge_prompt.md", "cases.yaml")]

PREFIX = ("Work only inside {ws}. Run every shell command with `HOME={home}` set (a sandbox home outside the repo). "
          "I'm the user; I'll answer your messages.\n\n")
MAX_TURNS, TURN_TIMEOUT_S, CASE_CEILING_S = 14, 900, 2700
INSTALL_RE = re.compile(r"\b(pip3?|uv)\s+(install|add|sync|pip)\b|python3?\s+-m\s+(venv|pip)\b|\bvirtualenv\b|"
                        r"\bpoetry\s+(add|install)\b|\bconda\s+(install|create)\b")
LOGIN_RE = re.compile(r"login\.py|resim\s+(auth|login)|DeviceCodeClient\(")
HEADINGS = ["Current state", "Intent", "Control", "Mapping", "Integration", "Data profile",
            "Metrics plan", "Config", "Verification"]
ONBOARD_SECTIONS = HEADINGS[:5]
JUDGE_CRITERIA = ["grounded_opening", "one_question", "plain_language", "decisions_confirmed", "intent",
                  "shape_form", "open_items", "traps_avoided", "routing", "brief_quality", "user_fit"]
CRITICAL = ["decisions_confirmed", "intent", "shape_form", "traps_avoided", "routing", "brief_quality"]
CHECKS = ["brief_written", "brief_headings", "brief_onboard_filled", "mapping_attributed",
          "next_skills", "no_install_before_brief", "no_login", "branch_from_user"]  # no_login: before the brief
_lock = threading.Lock()


# ---------------------------------------------------------------- harness gate
def harness_sha() -> str:
    h = hashlib.sha256()
    for f in HARNESS_FILES:
        h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def state_path() -> Path:
    return FLOW / "_state.json"


def load_state() -> dict:
    return json.loads(state_path().read_text()) if state_path().exists() else {}


# ---------------------------------------------------------------- workspace
def make_workspace(fixture: str, name: str) -> Path:
    src = SKT / "fixtures" / fixture
    if not src.is_dir():
        raise RuntimeError(f"fixture missing: {fixture}")
    ws = WORK / name
    for d in (ws, ws.parent / (ws.name + ".home")):
        if d.exists():
            shutil.rmtree(d)
    shutil.copytree(src, ws, ignore=shutil.ignore_patterns("_post_commit"))
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("init", "-q"); git("add", "-A")
    git("-c", "user.name=eval", "-c", "user.email=eval@example.com", "commit", "-qm", "fixture")
    if (src / "_post_commit").is_dir():  # dirty-tree fixtures: overlay after the commit
        shutil.copytree(src / "_post_commit", ws, dirs_exist_ok=True)
    home_dir(ws).mkdir(parents=True, exist_ok=True)  # outside the repo: a home/ inside breaks packaging
    clear_session_store(ws)
    return ws


def clear_session_store(ws: Path) -> None:
    """Remove the session log/memory Claude Code keeps for this eval workspace under ~/.claude/projects."""
    d = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(ws))
    if d.is_dir() and "sf-eval-work" in d.name:
        shutil.rmtree(d)


def home_dir(ws: Path) -> Path:
    return ws.parent / (ws.name + ".home")


def brief_snapshot(ws: Path) -> dict:
    return {p: Path(p).read_text() for p in sorted(glob.glob(str(ws / "docs" / "signalflag" / "*.md")))}


def file_list(ws: Path, limit=200) -> str:
    out = []
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws)
        if rel.parts[0] == ".git" or p.is_dir():
            continue
        out.append(f"{rel} ({p.stat().st_size} B)")
    return "\n".join(out[:limit]) + (f"\n... {len(out) - limit} more" if len(out) > limit else "")


# ---------------------------------------------------------------- claude calls
def run_claude(args, prompt, cwd, timeout):
    """Run `claude -p`; return (events, result_event). Retries with jittered backoff on overload/5xx."""
    attempts = 0
    while True:
        attempts += 1
        env = {**os.environ, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}  # no memory carried across runs/retries
        p = subprocess.run([CLAUDE, "-p", prompt, *args], cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        lines = [l for l in p.stdout.splitlines() if l.strip().startswith("{")]
        events = []
        for l in lines:
            try:
                events.append(json.loads(l))
            except json.JSONDecodeError:
                pass
        res = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if res is None and len(events) == 1 and "result" in events[0]:
            res = events[0]
        transient = res is None or (res.get("is_error") and re.search(
            r"overload|529|rate.?limit|429|5\d\d|timeout", json.dumps(res.get("result", "")), re.I))
        if not transient or attempts >= 4:
            if res is None:
                raise RuntimeError(f"claude produced no result (rc={p.returncode}): {p.stderr[-800:]}")
            res["_attempts"] = attempts
            return events, res
        time.sleep(min(60, 2 ** attempts) * (0.5 + random.random()))


_plugin_snap = None


def plugin_dir() -> Path:
    """The plugin as users install it: manifest, skills, .mcp.json. Not tests/ or .claude/ (answers, grades)."""
    global _plugin_snap
    with _lock:
        if _plugin_snap is None:
            d = Path(tempfile.mkdtemp(prefix="sf-plugin-")) / "signalskills"
            ref = os.environ.get("SF_PLUGIN_REF")  # e.g. HEAD: the committed skills, for a before/after
            if ref:
                d.mkdir(parents=True)
                arc = subprocess.run(["git", "-C", str(REPO), "archive", ref, ".claude-plugin", "skills", ".mcp.json"],
                                     check=True, capture_output=True).stdout
                subprocess.run(["tar", "-x", "-C", str(d)], input=arc, check=True)
            else:
                for name in (".claude-plugin", "skills"):
                    shutil.copytree(REPO / name, d / name)
                if (REPO / ".mcp.json").exists():
                    shutil.copy(REPO / ".mcp.json", d / ".mcp.json")
            _plugin_snap = d
    return _plugin_snap


def agent_args(model, session, first):
    a = ["--model", model, "--output-format", "stream-json", "--verbose",
         "--setting-sources", "project,local", "--plugin-dir", str(plugin_dir()),
         "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
         "--allowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill", "TodoWrite", "NotebookEdit",
         "--disallowedTools", "AskUserQuestion", "WebFetch", "WebSearch", "Agent", "Task"]
    return a + (["--session-id", session] if first else ["--resume", session])


def side_call(model, system, prompt, schema, timeout=300, effort=None):
    """Stateless persona/judge call: no tools, no settings, structured output."""
    with tempfile.TemporaryDirectory() as d:
        _, res = run_claude(["--model", model, "--output-format", "json", "--tools", "",
                             "--setting-sources", "local", "--strict-mcp-config",
                             "--mcp-config", '{"mcpServers":{}}', "--system-prompt", system,
                             "--json-schema", json.dumps(schema), "--no-session-persistence",
                             *(["--effort", effort] if effort else [])],
                            prompt, d, timeout)
    if res.get("is_error"):
        raise RuntimeError(f"side call failed: {str(res.get('result'))[:400]}")
    out = res.get("structured_output")
    if out is None:
        txt = res.get("result", "")
        m = re.search(r"\{.*\}", txt, re.S)
        out = json.loads(m.group(0)) if m else None
    if out is None:
        raise RuntimeError("side call returned no structured output")
    return out, res


def usage_of(res):
    u = res.get("usage") or {}
    return {k: u.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                     "cache_creation_input_tokens")}


def add_usage(a, b):
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


# ---------------------------------------------------------------- transcript
def events_to_turns(events):
    turns = []
    for e in events:
        if e.get("type") == "assistant":
            for b in e.get("message", {}).get("content", []):
                if b.get("type") == "text" and b.get("text", "").strip():
                    turns.append({"role": "assistant", "content": b["text"]})
                elif b.get("type") == "tool_use":
                    turns.append({"role": "tool_call", "name": b.get("name"),
                                  "content": json.dumps(b.get("input"), indent=2)})
        elif e.get("type") == "user":
            c = e.get("message", {}).get("content", [])
            for b in c if isinstance(c, list) else []:
                if b.get("type") == "tool_result":
                    cont = b.get("content")
                    if isinstance(cont, list):
                        cont = "\n".join(x.get("text", "") for x in cont if isinstance(x, dict))
                    turns.append({"role": "tool_result", "content": str(cont)[:6000]})
    return turns


def visible_agent_text(turns):
    return "\n\n".join(t["content"] for t in turns if t["role"] == "assistant")


def condensed(trace, max_result=300):
    out = []
    for t in trace:
        r = t["role"]
        if r == "user":
            out.append(f"USER: {t['content']}")
        elif r == "assistant":
            out.append(f"AGENT: {t['content']}")
        elif r == "tool_call":
            try:
                inp = json.loads(t["content"])
            except Exception:
                inp = {}
            short = inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("skill") or ""
            extra = ""
            if t["name"] in ("Write", "Edit") and "docs/signalflag" in str(short):
                extra = " [brief edit]"
            out.append(f"  [tool {t['name']}: {str(short)[:300]}]{extra}")
        elif r == "tool_result":
            out.append(f"  [result: {t['content'][:max_result].strip()}]")
    return "\n".join(out)


# ---------------------------------------------------------------- one case
def converse(case, ws, model, persona_model):
    session = str(uuid.uuid4())
    persona = case["persona"].strip()
    if not re.search(r"[Pp]roject:?\s*`", persona) and not case.get("project_unknown"):
        persona += "\nYour SignalFlag project is `acme-robotics`; it already exists."
    persona_sys = (HERE / "persona_prompt.md").read_text().replace("{persona}", persona)
    persona_schema = {"type": "object", "additionalProperties": False, "required": ["reply", "end", "end_reason"],
                      "properties": {"reply": {"type": "string"}, "end": {"type": "boolean"},
                                     "end_reason": {"type": "string"}}}
    trace = [{"role": "user", "content": case["prompt"]}]
    agent_usage, persona_usage = {}, {}
    agent_cost = persona_cost = 0.0
    models, attempts, end_reason = set(), 0, "max_turns"
    msg = PREFIX.format(ws=ws, home=home_dir(ws)) + case["prompt"]
    t0 = time.time()
    for turn in range(MAX_TURNS):
        if time.time() - t0 > CASE_CEILING_S:
            end_reason = "case_ceiling"; break
        events, res = run_claude(agent_args(model, session, turn == 0), msg, ws, TURN_TIMEOUT_S)
        attempts += res.get("_attempts", 1) - 1
        if res.get("is_error"):
            raise RuntimeError(f"agent turn {turn} errored: {str(res.get('result'))[:400]}")
        agent_usage = add_usage(agent_usage, usage_of(res))
        agent_cost += res.get("total_cost_usd") or 0.0
        models |= set((res.get("modelUsage") or {}).keys())
        turns = events_to_turns(events)
        trace += turns
        convo = "\n\n".join(f"{'YOU' if t['role'] == 'user' else 'AGENT'}: {t['content']}"
                            for t in trace if t["role"] in ("user", "assistant"))
        out, pres = side_call(persona_model, persona_sys,
                              f"<conversation>\n{convo}\n</conversation>\n\nYour next message:", persona_schema)
        persona_usage = add_usage(persona_usage, usage_of(pres))
        persona_cost += pres.get("total_cost_usd") or 0.0
        if out["end"]:
            end_reason = out["end_reason"] or "persona_end"; break
        trace.append({"role": "user", "content": out["reply"]})
        msg = out["reply"]
    if model not in models:
        raise RuntimeError(f"served models {sorted(models)} do not include requested {model}")
    return trace, {"agent_usage": agent_usage, "persona_usage": persona_usage, "agent_cost": agent_cost,
                   "persona_cost": persona_cost, "models": sorted(models), "turns": sum(
                       1 for t in trace if t["role"] == "user"), "retries": attempts,
                   "end_reason": end_reason, "session": session, "latency_s": round(time.time() - t0, 1)}


def expected_branch(case):
    m = re.search(r"[Bb]ranch[^`\n]*?`([^`]+)`", case["persona"])
    return m.group(1) if m else None


def checks(case, trace, before, after):
    new = {p: t for p, t in after.items() if p not in before and p.endswith("-brief.md")}
    changed = {p: t for p, t in after.items() if p in before and before[p] != t}
    expects_existing = case.get("brief") == "existing"
    targets = list(new.values()) + (list(changed.values()) if expects_existing else [])
    c = {}
    if expects_existing:
        c["brief_written"] = int(not new)  # no new brief when an approved one covers this test type
    else:
        c["brief_written"] = int(bool(new))
    def has_headings(t):
        return all(re.search(rf"^##\s+{re.escape(h)}\b", t, re.M) for h in HEADINGS)
    def section(t, h):
        m = re.search(rf"^##\s+{re.escape(h)}\b(.*?)(?=^##\s|\Z)", t, re.M | re.S)
        return (m.group(1) if m else "").strip()
    def filled(t):
        return all(section(t, h) and not section(t, h).startswith("_onboard") for h in ONBOARD_SECTIONS)
    nb = list(new.values())
    c["brief_headings"] = int(all(has_headings(t) for t in nb)) if nb else (1 if expects_existing else 0)
    c["brief_onboard_filled"] = int(all(filled(t) for t in nb)) if nb else (1 if expects_existing else 0)
    def attributed(t):
        """Branch / Test is / Version is items each say who decided (bold, wrapped lines tolerated)."""
        mp = section(t, "Mapping").replace("**", "")
        items = re.split(r"\n\s*-\s+", "\n" + mp)
        want = [i for i in items if re.match(r"(Branch|Test is|Version is)\b", i.strip())]
        return len(want) >= 3 and all(re.search(r"confirmed by user|chosen by agent|given by user|stated by user|"
                                                r"by user|user said|user chose", i, re.I) for i in want)
    c["mapping_attributed"] = int(all(attributed(t) for t in nb)) if nb else (1 if expects_existing else 0)
    # ordering: index of the first write to a brief file
    def writes_brief(t):
        if t["role"] != "tool_call" or "docs/signalflag" not in t["content"]:
            return False
        if t["name"] in ("Write", "Edit"):
            return True
        return t["name"] == "Bash" and bool(re.search(r">|\btee\b|open\(|sed -i|write_text", t["content"]))
    first_brief = next((i for i, t in enumerate(trace) if writes_brief(t)), len(trace))
    agent_text = visible_agent_text(trace)
    skills_after = [json.loads(t["content"]).get("skill", "") for i, t in enumerate(trace)
                    if t["role"] == "tool_call" and t["name"] == "Skill" and i > first_brief]
    routed = any(re.search(r"signalflag-(auth|design-metrics)$", sk) for sk in skills_after)
    order = [re.sub(r".*signalflag-", "", sk) for sk in skills_after]
    skipped_compose = "ingest" in order and ("compose-metrics" not in order or
                                             order.index("compose-metrics") > order.index("ingest"))
    route_line = bool(re.search(r"Next (skills?|steps?)\b", agent_text)) or bool(
        re.search(r"signalflag-\w[\w-]*\s*(→|->)\s*signalflag-", agent_text))
    if skills_after and re.search(r"signalflag-compose-metrics$", skills_after[0]):
        routed = False  # jumped past design-metrics
    c["next_skills"] = int((route_line or routed or expects_existing)
                           and not skipped_compose)
    cmds = [(i, json.loads(t["content"]).get("command", "")) for i, t in enumerate(trace)
            if t["role"] == "tool_call" and t["name"] == "Bash"]
    # before the brief exists: no SDK install (data readers are the judge's call: allowed only if asked) and no login
    c["no_install_before_brief"] = int(not any(INSTALL_RE.search(cmd) and re.search(r"signalflag", cmd)
                                               for i, cmd in cmds if i < first_brief))
    c["no_login"] = int(not any(LOGIN_RE.search(cmd) for i, cmd in cmds if i < first_brief))
    br = expected_branch(case)
    if br and nb:
        c["branch_from_user"] = int(all(re.search(rf"Branch:.*{re.escape(br)}", t) for t in nb))
    else:
        c["branch_from_user"] = None
    info = {"installs_total": sum(1 for _, cmd in cmds if INSTALL_RE.search(cmd)),
            "max_questions_in_msg": max([t["content"].count("?") for t in trace if t["role"] == "assistant"] or [0]),
            "tool_calls": sum(1 for t in trace if t["role"] == "tool_call")}
    return c, info, targets


def judge(case, trace, before, after, ws_files, judge_model):
    skill = (REPO / "skills" / "signalflag-onboard" / "SKILL.md").read_text()
    mapping = (REPO / "skills" / "signalflag-onboard" / "mapping.md").read_text()
    briefs = []
    for p, t in after.items():
        tag = "(new)" if p not in before else ("(modified)" if before[p] != t else "(unchanged)")
        briefs.append(f"--- {Path(p).name} {tag}\n{t}")
    prompt = (HERE / "judge_prompt.md").read_text()
    for k, v in {"{skill}": skill, "{mapping}": mapping, "{persona}": case["persona"].strip(),
                 "{expect}": yaml.safe_dump(case.get("expect", {}), sort_keys=False),
                 "{files}": ws_files, "{transcript}": condensed(trace),
                 "{briefs}": "\n\n".join(briefs) or "(none)"}.items():
        prompt = prompt.replace(k, v)
    crit = {"type": "object", "additionalProperties": False, "required": ["verdict", "why"],
            "properties": {"verdict": {"type": "string", "enum": ["pass", "fail", "na"]}, "why": {"type": "string"}}}
    schema = {"type": "object", "additionalProperties": False,
              "required": JUDGE_CRITERIA + ["overall", "top_issue"],
              "properties": {**{k: crit for k in JUDGE_CRITERIA},
                             "overall": {"type": "number"}, "top_issue": {"type": "string"}}}
    out, res = side_call(judge_model, "You are a strict, fair grader of agent transcripts. Output only the "
                         "requested JSON.", prompt, schema, timeout=600, effort="high")
    return out, res


JUDGE_SAMPLES = 3


def grade_row(case, trace, before, after, ws_files, judge_model):
    """Checks + majority of JUDGE_SAMPLES independent judge calls per criterion (ties -> fail)."""
    c, info, _ = checks(case, trace, before, after)
    with cf.ThreadPoolExecutor(JUDGE_SAMPLES) as ex:
        outs = list(ex.map(lambda _: judge(case, trace, before, after, ws_files, judge_model), range(JUDGE_SAMPLES)))
    js = [o for o, _ in outs]
    jres = {"usage": {}, "total_cost_usd": 0.0}
    for _, r in outs:
        jres["usage"] = add_usage(jres["usage"], usage_of(r)); jres["total_cost_usd"] += r.get("total_cost_usd") or 0
    grade, expl = {}, {}
    for k in JUDGE_CRITERIA:
        votes = [j[k]["verdict"] for j in js]
        win = max(("pass", "fail", "na"), key=lambda v: (votes.count(v), v == "fail"))
        grade[k] = None if win == "na" else int(win == "pass")
        expl[k] = f"[{votes.count('pass')}p/{votes.count('fail')}f/{votes.count('na')}na] " + \
            next(j[k]["why"] for j in js if j[k]["verdict"] == win)
    j = {"overall": sorted(x["overall"] for x in js)[len(js) // 2],
         "top_issue": " | ".join(x["top_issue"] for x in js)}
    for k in CHECKS:
        grade[f"chk_{k}"] = c[k]
    gates_ok = all(v in (1, None) for v in c.values())
    crit_ok = all(grade[k] in (1, None) for k in CRITICAL)
    grade["pass"] = int(gates_ok and crit_ok)
    applicable = [grade[k] for k in JUDGE_CRITERIA if grade[k] is not None]
    grade["rubric"] = round(sum(applicable) / len(applicable), 3) if applicable else None
    grade["overall"] = j["overall"]
    expl["overall"] = j["top_issue"]
    return grade, expl, info, jres


# ---------------------------------------------------------------- driver
def run_one(case, rep, variant, args):
    vdir = FLOW / variant
    name = f"{variant}-{case['id']}-r{rep}"
    ws = make_workspace(case["fixture"], name)
    before = brief_snapshot(ws)
    ws_files = file_list(ws)
    try:
        trace, meta = converse(case, ws, args.model, args.persona_model)
    finally:
        clear_session_store(ws)
    after = brief_snapshot(ws)
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    (vdir / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=1))
    snap = {"before": before, "after": after, "files": ws_files, "ws": str(ws)}
    (vdir / "traces" / f"{case['id']}_rep{rep}.state.json").write_text(json.dumps(snap))
    grade, expl, info, jres = grade_row(case, trace, before, after, ws_files, args.judge_model)
    return make_row(case, rep, grade, expl, info, meta, jres, args)


def make_row(case, rep, grade, expl, info, meta, jres, args):
    usage = add_usage(meta["agent_usage"], meta["persona_usage"])
    return {"prompt_id": case["id"], "rep": rep, "prompt": case["prompt"], "tags": case.get("tags", []),
            "status": "ok", "stop_reason": meta["end_reason"], "grade": grade, "explanation": expl,
            "model": args.model, "served_models": meta["models"], "usage": usage,
            "judge_model": args.judge_model, "judge_usage": usage_of(jres),
            "cost_usd": round(meta["agent_cost"] + meta["persona_cost"] + (jres.get("total_cost_usd") or 0), 4),
            "agent_cost_usd": round(meta["agent_cost"], 4),
            "latency_s": meta["latency_s"], "tool_calls": info["tool_calls"], "turns": meta["turns"],
            "meta": {**info, "session": meta["session"], "retries": meta["retries"],
                     "plugin_sha": plugin_sha(), "split": case.get("split")}}


def plugin_sha():
    out = subprocess.run(["git", "-C", str(REPO), "diff", "HEAD", "--", "skills"], capture_output=True, text=True)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return head.stdout.strip() + ("+" + hashlib.sha256(out.stdout.encode()).hexdigest()[:8] if out.stdout else "")


def append(path, row):
    with _lock, open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def done_keys(path):
    if not path.exists():
        return set()
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return {(r["prompt_id"], r["rep"]) for r in rows}


def regrade(variant, cases, args):
    vdir = FLOW / variant
    rows = [json.loads(l) for l in (vdir / "results.jsonl").read_text().splitlines() if l.strip()]
    by_id = {c["id"]: c for c in cases}
    out = []
    def one(r):
        case = by_id[r["prompt_id"]]
        trace = json.loads((vdir / "traces" / f"{r['prompt_id']}_rep{r['rep']}.json").read_text())
        st = json.loads((vdir / "traces" / f"{r['prompt_id']}_rep{r['rep']}.state.json").read_text())
        try:
            grade, expl, info, jres = grade_row(case, trace, st["before"], st["after"], st["files"], args.judge_model)
        except Exception as e:  # keep the previous grade; record the failure
            append(vdir / "errors.jsonl", {"prompt_id": r["prompt_id"], "rep": r["rep"], "class": "regrade_" +
                                           type(e).__name__, "error": str(e)[:2000]})
            return r
        r.update(grade=grade, explanation=expl, judge_usage=usage_of(jres))
        return r
    with cf.ThreadPoolExecutor(args.concurrency) as ex:
        out = list(ex.map(one, rows))
    shutil.copy(vdir / "results.jsonl", vdir / f"results.pre-regrade-{int(time.time())}.jsonl")
    (vdir / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out))
    print(f"regraded {len(out)} rows")


def summarize(variant):
    vdir = FLOW / variant
    rows = [json.loads(l) for l in (vdir / "results.jsonl").read_text().splitlines() if l.strip()]
    if not rows:
        return
    import math
    p = [r["grade"]["pass"] for r in rows]
    n = len(p); m = sum(p) / n
    half = 1.96 * math.sqrt(max(m * (1 - m), 1e-9) / n)
    rub = [r["grade"]["rubric"] for r in rows if r["grade"].get("rubric") is not None]
    cost = sum(r["cost_usd"] for r in rows)
    print(f"[{variant}] pass {m:.0%} ±{half:.0%} (n={n})  rubric {sum(rub) / len(rub):.2f}  "
          f"cost ${cost:.2f} (${cost / n:.2f}/run)")
    for k in JUDGE_CRITERIA + [f"chk_{c}" for c in CHECKS]:
        vals = [r["grade"].get(k) for r in rows if r["grade"].get(k) is not None]
        if vals:
            print(f"  {k:28s} {sum(vals)}/{len(vals)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--cases", default="")
    ap.add_argument("--split", default="", help="train|test: only cases in that split (from _state.json)")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--persona-model", default="claude-sonnet-5-5")
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    ap.add_argument("--regrade", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--approve-harness", action="store_true")
    args = ap.parse_args()

    FLOW.mkdir(parents=True, exist_ok=True)
    state = load_state()
    if args.approve_harness:
        state["harness_sha"] = harness_sha()
        state_path().write_text(json.dumps(state, indent=2))
        print("harness approved:", state["harness_sha"][:12]); return
    if args.summary:
        summarize(args.variant); return
    # pilot* variants are runner-development runs (never compared or reported as a baseline): no gate
    if not args.variant.startswith("pilot") and state.get("harness_sha") != harness_sha():
        print("harness changed since last --approve-harness (run_eval.py, prompts or cases.yaml). "
              "Review the diff, then run: python run_eval.py --approve-harness", file=sys.stderr)
        sys.exit(2)

    cases = yaml.safe_load((HERE / "cases.yaml").read_text())
    split_ids = {"train": set(state.get("train_ids", [])), "test": set(state.get("test_ids", []))}
    for c in cases:
        c["split"] = "test" if c["id"] in split_ids["test"] else "train"
    if args.regrade:
        regrade(args.variant, cases, args); summarize(args.variant); return
    if args.cases:
        want = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in want]
    if args.split:
        cases = [c for c in cases if c["split"] == args.split]
    missing = [c["fixture"] for c in cases if not (SKT / "fixtures" / c["fixture"]).is_dir()]
    if missing:
        sys.exit(f"missing fixtures: {sorted(set(missing))}")

    vdir = FLOW / args.variant
    vdir.mkdir(parents=True, exist_ok=True)
    res_path, err_path = vdir / "results.jsonl", vdir / "errors.jsonl"
    done = done_keys(res_path)
    jobs = [(c, r) for c in cases for r in range(args.reps) if (c["id"], r) not in done]
    print(f"{len(jobs)} runs to do ({len(done)} already done) -> {vdir}", flush=True)
    t0, finished = time.time(), 0

    def work(job):
        case, rep = job
        try:
            row = run_one(case, rep, args.variant, args)
            append(res_path, row)
            return f"{case['id']} r{rep}: pass={row['grade']['pass']} rubric={row['grade']['rubric']} ${row['cost_usd']:.2f}"
        except Exception as e:  # harness failure: sidecar, never a scored row
            append(err_path, {"prompt_id": case["id"], "rep": rep, "class": type(e).__name__,
                              "error": str(e)[:2000], "at": dt.datetime.now().isoformat()})
            return f"{case['id']} r{rep}: ERROR {type(e).__name__}: {str(e)[:200]}"

    with cf.ThreadPoolExecutor(args.concurrency) as ex:
        for msg in ex.map(work, jobs):
            finished += 1
            el = time.time() - t0
            line = f"{finished}/{len(jobs)} done, {el / 60:.1f} min, ~{el / finished * (len(jobs) - finished) / 60:.0f} min left | {msg}"
            print(line, flush=True)
            (vdir / "progress.txt").write_text(line + "\n")
    summarize(args.variant)


if __name__ == "__main__":
    main()

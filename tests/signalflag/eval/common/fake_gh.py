"""Install a `gh` stand-in that records PRs. mode: ok | absent | unauthenticated."""
import json, stat
from pathlib import Path

SHIM = '''#!/usr/bin/env python3
import json, sys, os, subprocess
log = os.environ.get("FAKE_GH_LOG") or {log!r}
mode = {mode!r}
a = sys.argv[1:]
if mode == "absent":
    print("gh: command not found", file=sys.stderr); sys.exit(127)
if a[:1] in (["--version"], ["version"]):
    print("gh version 2.62.0 (2024-11-14)"); sys.exit(0)
if a[:2] == ["auth", "status"]:
    sys.exit(0 if mode == "ok" else 1)
if mode != "ok":
    print("gh: not logged in to github.com. Run gh auth login.", file=sys.stderr); sys.exit(1)
def parse(args):
    names = {{"-t": "title", "--title": "title", "-b": "body", "--body": "body",
             "-F": "body-file", "--body-file": "body-file", "-B": "base", "--base": "base",
             "-H": "head", "--head": "head"}}
    opts, pos = {{}}, []; i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("--") and "=" in tok and tok.split("=", 1)[0] in names:
            k, v = tok.split("=", 1); opts[names[k]] = v; i += 1
        elif tok in names and i + 1 < len(args):
            opts[names[tok]] = args[i + 1]; i += 2
        else:
            if not tok.startswith("-"):
                pos.append(tok)
            i += 1   # value-less flag (--draft, --fill, --web) or unknown: tolerated
    if "body-file" in opts:
        f = opts.pop("body-file")
        opts["body"] = sys.stdin.read() if f == "-" else open(f).read()
    return opts, pos
if a[:2] == ["pr", "edit"]:
    opts, pos = parse(a[2:])
    prs = [json.loads(l) for l in open(log).read().splitlines() if l.strip()] if os.path.exists(log) else []
    if not prs:
        print("no pull requests found", file=sys.stderr); sys.exit(1)
    ref = pos[0] if pos else None
    hit = [p for p in prs if ref is None or str(p["number"]) == ref.lstrip("#").rsplit("/", 1)[-1] or p["head"] == ref]
    if not hit:
        print(f"no pull requests found for {{ref}}", file=sys.stderr); sys.exit(1)
    hit[-1].update({{k: v for k, v in opts.items() if k in ("title", "body", "base")}})
    open(log, "w").write("".join(json.dumps(p) + "\\n" for p in prs))
    print(f"https://github.com/acme/planner/pull/{{hit[-1]['number']}}"); sys.exit(0)
if a[:2] == ["pr", "create"]:
    opts, _ = parse(a[2:])
    if not opts.get("head"):
        opts["head"] = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      capture_output=True, text=True).stdout.strip()
    opts.setdefault("base", "main")
    if any(t.startswith("--fill") for t in a):   # like gh: title/body from the head branch's commit(s)
        git_log = lambda f: subprocess.run(["git", "log", "-1", f"--format={{f}}", opts["head"]],
                                           capture_output=True, text=True).stdout.strip()
        opts.setdefault("title", git_log("%s")); opts.setdefault("body", git_log("%b"))
    opts.setdefault("title", ""); opts.setdefault("body", "")
    n = sum(1 for _ in open(log)) + 1 if os.path.exists(log) else 1
    opts["number"] = n
    os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
    open(log, "a").write(json.dumps(opts) + "\\n")
    print(f"https://github.com/acme/planner/pull/{{n}}"); sys.exit(0)
if a[:2] in (["pr", "list"], ["pr", "view"]):
    print(open(log).read() if os.path.exists(log) else ""); sys.exit(0)
print("gh (fake): unsupported " + " ".join(a), file=sys.stderr); sys.exit(1)
'''

def install_fake_gh(bin_dir: Path, log: Path, mode: str = "ok") -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    p = bin_dir / "gh"
    p.write_text(SHIM.format(log=str(log), mode=mode))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)

def read_prs(log: Path) -> list:
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()] if log.exists() else []

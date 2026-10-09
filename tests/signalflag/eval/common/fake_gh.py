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
if a[:2] == ["auth", "status"]:
    sys.exit(0 if mode == "ok" else 1)
if mode != "ok":
    print("gh: not logged in to github.com. Run gh auth login.", file=sys.stderr); sys.exit(1)
if a[:2] == ["pr", "create"]:
    names = {{"-t": "title", "--title": "title", "-b": "body", "--body": "body",
             "-F": "body-file", "--body-file": "body-file", "-B": "base", "--base": "base",
             "-H": "head", "--head": "head"}}
    opts = {{}}; i = 2
    while i < len(a):
        tok = a[i]
        if tok.startswith("--") and "=" in tok and tok.split("=", 1)[0] in names:
            k, v = tok.split("=", 1); opts[names[k]] = v; i += 1
        elif tok in names and i + 1 < len(a):
            opts[names[tok]] = a[i + 1]; i += 2
        else:
            i += 1   # value-less flag (--draft, --fill, --web) or unknown: tolerated
    if "body-file" in opts:
        f = opts.pop("body-file")
        opts["body"] = sys.stdin.read() if f == "-" else open(f).read()
    if not opts.get("head"):
        opts["head"] = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                      capture_output=True, text=True).stdout.strip()
    opts.setdefault("base", "main")
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

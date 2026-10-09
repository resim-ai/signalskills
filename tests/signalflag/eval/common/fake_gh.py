"""Install a `gh` stand-in that records PRs. mode: ok | absent | unauthenticated."""
import json, stat
from pathlib import Path

SHIM = '''#!/usr/bin/env python3
import json, sys, os
log = os.environ.get("FAKE_GH_LOG") or {log!r}
mode = {mode!r}
a = sys.argv[1:]
if a[:2] == ["auth", "status"]:
    sys.exit(0 if mode == "ok" else 1)
if mode != "ok":
    print("gh: not logged in to github.com. Run gh auth login.", file=sys.stderr); sys.exit(1)
if a[:2] == ["pr", "create"]:
    opts = {{}}; i = 2
    while i < len(a):
        if a[i].startswith("--") and i + 1 < len(a) and not a[i + 1].startswith("--"):
            opts[a[i][2:]] = a[i + 1]; i += 2
        else:
            opts[a[i].lstrip("-")] = True; i += 1
    if "body-file" in opts:
        opts["body"] = open(opts["body-file"]).read()
    n = sum(1 for _ in open(log)) + 1 if os.path.exists(log) else 1
    opts["number"] = n
    open(log, "a").write(json.dumps(opts) + "\\n")
    print(f"https://github.com/acme/planner/pull/{{n}}"); sys.exit(0)
if a[:2] in (["pr", "list"], ["pr", "view"]):
    print(open(log).read() if os.path.exists(log) else ""); sys.exit(0)
print("gh (fake): unsupported " + " ".join(a), file=sys.stderr); sys.exit(1)
'''

def install_fake_gh(bin_dir: Path, log: Path, mode: str = "ok") -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    if mode == "absent":
        return
    p = bin_dir / "gh"
    p.write_text(SHIM.format(log=str(log), mode=mode))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)

def read_prs(log: Path) -> list:
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()] if log.exists() else []

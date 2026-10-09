"""A bare git remote that stands in for GitHub, and CI simulated as 'upload from a clean checkout of main'."""
import os, shutil, subprocess, tempfile
from pathlib import Path

def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout

def add_bare_remote(ws: Path) -> Path:
    remote = ws.parent / (ws.name + ".remote.git")
    if remote.exists():
        shutil.rmtree(remote)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    _git(ws, "remote", "add", "origin", str(remote))
    _git(ws, "push", "-q", "-u", "origin", "main")
    return remote

def merge_pr_branch(ws: Path, head: str) -> None:
    """What clicking Merge does: main in the remote gains the PR branch.

    Then `git fetch origin` in ws so origin/main is current. Local branches are not touched."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", _git(ws, "remote", "get-url", "origin").strip(), "m")
        m = Path(d) / "m"
        _git(m, "-c", "user.name=merge", "-c", "user.email=m@m", "merge", "-q", "--no-ff", "-m", f"Merge {head}", f"origin/{head}")
        _git(m, "push", "-q", "origin", "main")
    _git(ws, "fetch", "-q", "origin")

def simulate_ci(ws: Path, upload_cmd: str, env: dict) -> str:
    """Run the upload the way CI does: a clean checkout of origin/main, nothing from the working tree.

    Returns stdout+stderr followed by a final line `[ci exit <returncode>]`."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", "--branch", "main", _git(ws, "remote", "get-url", "origin").strip(), "ci")
        r = subprocess.run(upload_cmd, shell=True, cwd=Path(d) / "ci", capture_output=True, text=True,
                           env={**os.environ, **env}, timeout=600)
        out = r.stdout + r.stderr
        if out and not out.endswith("\n"):
            out += "\n"
        return out + f"[ci exit {r.returncode}]"

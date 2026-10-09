"""A bare git remote that stands in for GitHub, and CI simulated as 'upload from a clean checkout of main'."""
import shutil, subprocess, tempfile
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
    """What clicking Merge does: main in the remote gains the PR branch."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", _git(ws, "remote", "get-url", "origin").strip(), "m")
        m = Path(d) / "m"
        _git(m, "-c", "user.name=merge", "-c", "user.email=m@m", "merge", "-q", "--no-ff", "-m", f"Merge {head}", f"origin/{head}")
        _git(m, "push", "-q", "origin", "main")

def simulate_ci(ws: Path, upload_cmd: str, env: dict) -> str:
    """Run the upload the way CI does: a clean checkout of origin/main, nothing from the working tree."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", "--branch", "main", _git(ws, "remote", "get-url", "origin").strip(), "ci")
        r = subprocess.run(upload_cmd, shell=True, cwd=Path(d) / "ci", capture_output=True, text=True,
                           env={**__import__("os").environ, **env}, timeout=600)
        return r.stdout + r.stderr

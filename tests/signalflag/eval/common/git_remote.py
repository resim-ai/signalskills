"""A bare git remote that stands in for GitHub, and CI simulated as 'upload from a clean checkout of main'.

`origin` reads as GitHub (`git remote -v` shows GITHUB_URL). Transport goes through a fake ssh (core.sshCommand) that
runs git's pack commands against the local bare repo, so nothing ever reaches the network. (`url.<path>.insteadOf`
was not used: `git remote -v` prints the rewritten local path, which gives the stand-in away.)"""
import os, shutil, stat, subprocess, tempfile
from pathlib import Path

GITHUB_URL = "git@github.com:acme/planner.git"

_FAKE_SSH = """#!/bin/sh
# Stand-in for ssh to github.com: git calls `<this> git@github.com "git-upload-pack 'acme/planner.git'"`.
# Runs the pack command locally against the bare repo. Any other host or repo is refused: it never opens a connection.
[ "$#" -ge 2 ] || {{ echo "fake ssh: no connection allowed" >&2; exit 255; }}
for last; do :; done
eval "host=\\${{$(($# - 1))}}"
[ "$host" = "git@github.com" ] || {{ echo "fake ssh: refusing host $host" >&2; exit 255; }}
case "$last" in
  "git-upload-pack 'acme/planner.git'"|"git-upload-pack '/acme/planner.git'") ;;
  "git-receive-pack 'acme/planner.git'"|"git-receive-pack '/acme/planner.git'") ;;
  *) echo "fake ssh: refusing $last" >&2; exit 255 ;;
esac
exec sh -c "${{last%% *}} '{bare}'"
"""


class NotMergeable(Exception):
    """The PR can't be merged for a reason that is the agent's (a conflict, or its branch was never pushed)."""


def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout


def bare_path(ws: Path) -> Path:
    return ws.parent / (ws.name + ".remote.git")


def fake_ssh(ws: Path) -> Path:
    return ws.parent / (ws.name + ".ssh")


def ssh_env(ws: Path) -> dict:
    """Env that routes every ssh git does through the fake ssh (which refuses anything but origin): no network."""
    s = str(fake_ssh(ws).resolve())
    return {"GIT_SSH_COMMAND": s, "GIT_SSH": s, "GIT_SSH_VARIANT": "simple"}


def add_bare_remote(ws: Path) -> Path:
    remote = bare_path(ws)
    if remote.exists():
        shutil.rmtree(remote)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    ssh = fake_ssh(ws)
    ssh.write_text(_FAKE_SSH.format(bare=remote))
    ssh.chmod(ssh.stat().st_mode | stat.S_IEXEC)
    _git(ws, "remote", "add", "origin", GITHUB_URL)
    _git(ws, "config", "core.sshCommand", str(ssh))
    _git(ws, "config", "ssh.variant", "simple")   # no `-G` probe, no -o/-p options
    _git(ws, "push", "-q", "-u", "origin", "main")
    return remote


def merge_pr_branch(ws: Path, head: str) -> None:
    """What clicking Merge does: main in the remote gains the PR branch.

    Then `git fetch origin` in ws so origin/main is current. Local branches are not touched.
    Raises NotMergeable for the agent's problems (branch not pushed, conflict); anything else is the harness's."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", str(bare_path(ws)), "m")
        m = Path(d) / "m"
        if subprocess.run(["git", "-C", str(m), "rev-parse", "--verify", "-q", f"origin/{head}"],
                          capture_output=True).returncode:
            raise NotMergeable(f"branch {head!r} is not on origin")
        r = subprocess.run(["git", "-C", str(m), "-c", "user.name=merge", "-c", "user.email=m@m", "merge", "-q",
                            "--no-ff", "-m", f"Merge {head}", f"origin/{head}"], capture_output=True, text=True)
        if r.returncode:
            if _git(m, "diff", "--name-only", "--diff-filter=U").strip():
                raise NotMergeable(f"merge conflict: {(r.stdout + r.stderr)[-400:]}")
            raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
        _git(m, "push", "-q", "origin", "main")
    _git(ws, "fetch", "-q", "origin")


def simulate_ci(ws: Path, upload_cmd: str, env: dict) -> str:
    """Run the upload the way CI does: a clean checkout of origin/main, nothing from the working tree.

    Returns stdout+stderr followed by a final line `[ci exit <returncode>]`."""
    with tempfile.TemporaryDirectory() as d:
        _git(d, "clone", "-q", "--branch", "main", str(bare_path(ws)), "ci")
        env = {**os.environ, **(ssh_env(ws) if fake_ssh(ws).exists() else {}), **env}
        r = subprocess.run(upload_cmd, shell=True, cwd=Path(d) / "ci", capture_output=True, text=True,
                           env=env, timeout=600)
        out = r.stdout + r.stderr
        if out and not out.endswith("\n"):
            out += "\n"
        return out + f"[ci exit {r.returncode}]"

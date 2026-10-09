import json, subprocess
from pathlib import Path
from common.git_remote import add_bare_remote, merge_pr_branch, simulate_ci
from common.fake_gh import install_fake_gh, read_prs

def _repo(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "cfg.yml").write_text("a: 1\n")
    for c in (["init", "-q", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(ws), *c], check=True)
    return ws

def test_remote_pr_merge_and_ci(tmp_path):
    ws = _repo(tmp_path); remote = add_bare_remote(ws)
    bin_dir, log = tmp_path / "bin", tmp_path / "gh.jsonl"
    install_fake_gh(bin_dir, log)
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("checkout", "-qb", "feat"); (ws / "cfg.yml").write_text("a: 2\n"); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "x"); git("push", "-q", "origin", "feat")
    out = subprocess.run([str(bin_dir / "gh"), "pr", "create", "--base", "main", "--head", "feat", "--title", "t", "--body", "b"],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "pull/1" in out.stdout
    assert read_prs(log)[0]["head"] == "feat"
    assert "a: 1" in simulate_ci(ws, "cat cfg.yml", {})          # CI sees main, not the PR
    merge_pr_branch(ws, "feat")
    assert "a: 2" in simulate_ci(ws, "cat cfg.yml", {})          # after merge, CI sees the change

def test_gh_absent_and_unauthenticated(tmp_path):
    for mode, code in (("absent", 127), ("unauthenticated", 1)):
        b = tmp_path / mode; install_fake_gh(b, tmp_path / f"{mode}.jsonl", mode=mode)
        r = subprocess.run([str(b / "gh"), "auth", "status"], capture_output=True, text=True)
        assert r.returncode == code
        if mode == "absent":
            assert "command not found" in r.stderr


def _gh(tmp_path, *args, cwd=None):
    b, log = tmp_path / "bin", tmp_path / "sub" / "gh.jsonl"
    install_fake_gh(b, log)
    r = subprocess.run([str(b / "gh"), "pr", "create", *args], capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, r.stderr
    return read_prs(log)[0]

def test_pr_create_defaults_to_current_branch(tmp_path):
    ws = _repo(tmp_path)
    subprocess.run(["git", "-C", str(ws), "checkout", "-qb", "my-branch"], check=True)
    pr = _gh(tmp_path, "--draft", "--fill", cwd=ws)
    assert pr["head"] == "my-branch" and pr["base"] == "main" and pr["title"] == "" and pr["body"] == ""

def test_pr_create_short_and_equals_forms(tmp_path):
    pr = _gh(tmp_path, "-H", "feat", "-t", "T", "-b", "---")
    assert (pr["head"], pr["title"], pr["body"]) == ("feat", "T", "---")
    (tmp_path / "x").mkdir()
    pr = _gh(tmp_path / "x", "--head=feat", "--title=T2", "--base=dev")
    assert (pr["head"], pr["title"], pr["base"]) == ("feat", "T2", "dev")

def test_pr_create_body_file(tmp_path):
    f = tmp_path / "body.md"; f.write_text("hello\nworld\n")
    pr = _gh(tmp_path, "--head", "feat", "-F", str(f))
    assert pr["body"] == "hello\nworld\n"

def test_simulate_ci_reports_exit_code(tmp_path):
    ws = _repo(tmp_path); add_bare_remote(ws)
    out = simulate_ci(ws, "cat cfg.yml", {})
    assert out.endswith("[ci exit 0]")
    assert simulate_ci(ws, "exit 3", {}).endswith("[ci exit 3]")

def test_merge_updates_origin_main(tmp_path):
    ws = _repo(tmp_path); add_bare_remote(ws)
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True, text=True).stdout
    git("checkout", "-qb", "feat"); (ws / "cfg.yml").write_text("a: 2\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "x"); git("push", "-q", "origin", "feat")
    sha = git("rev-parse", "feat").strip()
    merge_pr_branch(ws, "feat")
    assert git("merge-base", "--is-ancestor", sha, "origin/main") == ""

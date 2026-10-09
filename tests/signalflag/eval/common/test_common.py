import json, subprocess
from pathlib import Path
from common.git_remote import GITHUB_URL, NotMergeable, add_bare_remote, merge_pr_branch, simulate_ci
import pytest
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
    assert pr["head"] == "my-branch" and pr["base"] == "main" and pr["title"] == "init" and pr["body"] == ""  # --fill: from the commit

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


def test_pr_edit_updates_record(tmp_path):
    b, log = tmp_path / "bin", tmp_path / "gh.jsonl"
    install_fake_gh(b, log)
    run = lambda *a, **k: subprocess.run([str(b / "gh"), *a], capture_output=True, text=True, **k)
    assert run("pr", "create", "--head", "feat", "--title", "t", "--body", "x").returncode == 0
    r = run("pr", "edit", "1", "--body-file", "-", input="real body\n")
    assert r.returncode == 0, r.stderr
    assert run("pr", "edit", "feat", "--title", "t2").returncode == 0
    assert run("pr", "edit", "7", "--title", "t3").returncode == 1
    pr = read_prs(log)[0]
    assert (pr["body"], pr["title"], pr["head"], pr["number"]) == ("real body\n", "t2", "feat", 1)


def test_pr_create_fill_uses_commit(tmp_path):
    ws = _repo(tmp_path)
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("checkout", "-qb", "feat"); (ws / "cfg.yml").write_text("a: 3\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "Add chart\n\nWhy it matters.")
    b, log = tmp_path / "bin", tmp_path / "gh.jsonl"
    install_fake_gh(b, log)
    r = subprocess.run([str(b / "gh"), "pr", "create", "--fill"], capture_output=True, text=True, cwd=ws)
    assert r.returncode == 0, r.stderr
    pr = read_prs(log)[0]
    assert (pr["head"], pr["title"], pr["body"]) == ("feat", "Add chart", "Why it matters.")


def test_version(tmp_path):
    for mode, code in (("ok", 0), ("unauthenticated", 0), ("absent", 127)):
        b = tmp_path / mode; install_fake_gh(b, tmp_path / f"{mode}.jsonl", mode=mode)
        assert subprocess.run([str(b / "gh"), "--version"], capture_output=True).returncode == code


def test_origin_reads_as_github_and_pushes_locally(tmp_path):
    ws = _repo(tmp_path); remote = add_bare_remote(ws)
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True, text=True).stdout
    assert git("remote", "-v").split()[1] == GITHUB_URL and str(remote) not in git("remote", "-v")
    git("checkout", "-qb", "feat"); git("push", "-q", "origin", "feat")
    assert "refs/heads/feat" in subprocess.run(["git", "-C", str(remote), "show-ref"], capture_output=True,
                                               text=True).stdout
    git("fetch", "-q", "origin"); assert "origin/feat" in git("branch", "-r")


def test_merge_not_mergeable(tmp_path):
    ws = _repo(tmp_path); add_bare_remote(ws)
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True, text=True).stdout
    with pytest.raises(NotMergeable, match="not on origin"):
        merge_pr_branch(ws, "never-pushed")
    git("checkout", "-qb", "feat"); (ws / "cfg.yml").write_text("a: 2\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "x"); git("push", "-q", "origin", "feat")
    git("checkout", "-q", "main"); (ws / "cfg.yml").write_text("a: 9\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "y"); git("push", "-q", "origin", "main")
    with pytest.raises(NotMergeable, match="conflict"):
        merge_pr_branch(ws, "feat")


def test_pr_view_list_repo_view_and_edit_flags(tmp_path):
    b, log = tmp_path / "bin", tmp_path / "gh.jsonl"
    install_fake_gh(b, log)
    run = lambda *a, **k: subprocess.run([str(b / "gh"), *a], capture_output=True, text=True, **k)
    assert run("pr", "create", "--head", "feat", "--title", "T", "--body", "B").returncode == 0
    assert run("pr", "edit", "--add-label", "x", "--body", "B2").returncode == 0      # no ref: last PR; label ignored
    assert read_prs(log)[0]["body"] == "B2"
    v = json.loads(run("pr", "view", "1", "--json", "title,body,url").stdout)
    assert (v["title"], v["body"], v["headRefName"]) == ("T", "B2", "feat")
    assert "T #1" in run("pr", "view", "feat").stdout
    assert run("pr", "list").stdout.startswith("1\tT\tfeat")
    assert json.loads(run("repo", "view", "--json", "nameWithOwner").stdout)["nameWithOwner"] == "acme/planner"


def test_two_prs_and_edit_keep_one_record_per_line(tmp_path):
    b, log = tmp_path / "bin", tmp_path / "gh.jsonl"
    install_fake_gh(b, log)
    run = lambda *a: subprocess.run([str(b / "gh"), *a], capture_output=True, text=True)
    run("pr", "create", "--head", "a", "--title", "A"); run("pr", "create", "--head", "b", "--title", "B")
    assert run("pr", "edit", "1", "--title", "A2").returncode == 0
    assert [(p["number"], p["title"]) for p in read_prs(log)] == [(1, "A2"), (2, "B")]


def test_fake_ssh_refuses_other_remotes(tmp_path):
    from common.git_remote import ssh_env
    import os
    ws = _repo(tmp_path); add_bare_remote(ws)
    env = {**os.environ, **ssh_env(ws)}
    for url in ("git@github.com:other/x.git", "git@gitlab.com:acme/planner.git", "ssh://git@github.com/other/x.git"):
        r = subprocess.run(["git", "ls-remote", url], capture_output=True, text=True, env=env, timeout=20)
        assert r.returncode != 0 and "fake ssh: refusing" in r.stderr, (url, r.stderr)
    r = subprocess.run(["git", "ls-remote", GITHUB_URL], capture_output=True, text=True, env=env, timeout=20)
    assert r.returncode == 0 and "refs/heads/main" in r.stdout

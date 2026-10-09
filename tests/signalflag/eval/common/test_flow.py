import subprocess
from common import flow
from common.git_remote import add_bare_remote


def _ws(tmp_path, files):
    ws = tmp_path / "ws"; ws.mkdir()
    for k, v in files.items():
        (ws / k).parent.mkdir(parents=True, exist_ok=True); (ws / k).write_text(v)
    for c in (["init", "-q", "-b", "main"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed"]):
        subprocess.run(["git", "-C", str(ws), *c], check=True)
    flow.install_github(ws, "ok")
    return ws


def test_pr_opened_modes():
    trace = [{"role": "assistant", "content": "Here's the PR:\n\nTitle: Add SignalFlag upload\n\nBody ..."}]
    st = {"prs": [{"head": "f", "base": "main", "body": "b"}]}
    assert flow.pr_opened({}, st, trace) == (1, "b")
    assert flow.pr_opened({}, {**st, "agent_pushed_main": True}, trace)[0] == 0
    assert flow.pr_opened({"gh": "absent"}, {"remote_branches": ["f"]}, trace)[0] == 1
    assert flow.pr_opened({"gh": "absent"}, {"remote_branches": []}, trace)[0] == 0


def test_run_ci_without_plugin_is_skipped_when_allowed(tmp_path):
    ws = _ws(tmp_path, {"a.txt": "x"})
    state, seed = {}, flow.mark_pushed_main(ws, {})
    assert flow.run_ci(ws, "p", "b", "true", state, "ci", lambda: None, seed, plugin_required=False) is False
    assert state["ci"].startswith("[skipped")
    try:
        flow.run_ci(ws, "p", "b", "true", {}, "ci", lambda: None, seed)
        assert False, "plugin.py missing on main must be a harness error by default"
    except RuntimeError as e:
        assert "harness" in str(e)


def test_find_pr_head_and_merge(tmp_path):
    ws = _ws(tmp_path, {"a.txt": "x"})
    git = lambda *a: subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)
    git("checkout", "-qb", "feat"); (ws / "b.txt").write_text("y"); git("add", "b.txt")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b"); git("push", "-q", "origin", "feat")
    bin_dir, log = flow.gh_paths(ws)
    subprocess.run([str(bin_dir / "gh"), "pr", "create", "--head", "feat", "--title", "t", "--body", "b"],
                   check=True, capture_output=True, env={"FAKE_GH_LOG": str(log), "PATH": "/usr/bin:/bin"}, cwd=ws)
    state = {}
    flow.mark_pushed_main(ws, state)
    assert state["agent_pushed_main"] is False
    head = flow.find_pr_head(ws, {}, log, state, lambda: None)
    assert head == "feat" and state["remote_branches"] == ["feat"]
    assert flow.merge(ws, head, state, lambda: None) and state["pr_files"] == ["b.txt"]

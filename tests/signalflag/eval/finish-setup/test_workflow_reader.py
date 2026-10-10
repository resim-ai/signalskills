"""Workflow upload detection (always) and the LLM workflow reader on fixed inputs (SF_LLM_TESTS=1; ~15 Sonnet calls).

  cd tests/signalflag/eval/finish-setup && SF_LLM_TESTS=1 ../../.venv/bin/python -m pytest -q test_workflow_reader.py"""
import os
import pytest
import run_finish_setup_eval as m

REAL = "skilltest-fs-reader-real"
PLUGIN = (m.FIXTURE / "sf_pytest" / "plugin.py").read_text().replace('DEFAULT_BRANCH = "planner-pytest"',
                                                                      f'DEFAULT_BRANCH = "{REAL}"')
CONFTEST = 'pytest_plugins = ["sf_pytest.plugin"]\n'
PYPROJECT = (m.FIXTURE / "pyproject.toml").read_text()
ORIG = m.WORKFLOW_YML
SCHEDULE_ONLY = ORIG.replace("on:\n  push:\n    branches: [main]\n  pull_request:\n", "on:\n  schedule:\n    - cron: '0 3 * * *'\n")
NO_UPLOAD = ORIG.replace('        env:\n          SIGNALFLAG_UPLOAD: "1"\n', "")
PR_TO_REAL = ORIG.replace("        run: pytest -q\n", "        run: |\n          if [ \"${{ github.event_name }}\" = \"pull_request\" ]; "
                          f"then pytest -q --sf-branch {REAL}; else pytest -q; fi\n")
# pull_request runs use a dev default, but pyproject's addopts force the real branch
ADDOPTS_PLUGIN = PLUGIN.replace(f'DEFAULT_BRANCH = "{REAL}"', 'DEFAULT_BRANCH = "planner-dev"')
ADDOPTS_PYPROJECT = PYPROJECT + f'\n[tool.pytest.ini_options]\naddopts = "--sf-branch {REAL}"\n'
FIXED = ORIG.replace("        run: pytest -q\n", "        run: |\n          if [ \"${{ github.event_name }}\" = \"pull_request\" ]; "
                     f"then pytest -q --sf-branch {REAL}-pr-${{{{ github.event.number }}}}; else pytest -q; fi\n")

CASES = [  # (name, workflow, plugin, pyproject, expected)
    ("schedule-only", SCHEDULE_ONLY, PLUGIN, PYPROJECT, 1),
    ("pr-to-pr-branch", FIXED, PLUGIN, PYPROJECT, 1),
    ("sf-branch override to real on the PR run", PR_TO_REAL, PLUGIN, PYPROJECT, 0),
    ("addopts override to real for PR", ORIG, ADDOPTS_PLUGIN, ADDOPTS_PYPROJECT, 0),
    ("original fixture", ORIG, PLUGIN, PYPROJECT, 0),
]


def test_upload_detection():
    assert m.workflow_uploads({"w": ORIG})
    assert not m.workflow_uploads({"w": NO_UPLOAD})                       # pytest alone isn't an upload
    assert m.workflow_uploads({"w": NO_UPLOAD}, conftest='import os\nos.environ.setdefault("SIGNALFLAG_UPLOAD", "1")\n')
    assert m.workflow_uploads({"w": "steps:\n  - run: python ingest_runs.py --branch x\n"})


def test_upload_removed_passes_without_reader():
    st = {"prs": [{"head": "h", "base": "main", "body": "b"}], "pr_workflows": {m.WORKFLOW: NO_UPLOAD},
          "pr_files": [], "real_branch_before_merge": {"exists": False}}
    c, _, _ = m.checks({"workspace": "planner_ci_pr_uploads"}, [], {"__cfg__": {}}, {"__state__": st})
    assert c["pr_ci_off_real_branch"] == 1


@pytest.mark.skipif(os.environ.get("SF_LLM_TESTS") != "1", reason="LLM reader: set SF_LLM_TESTS=1")
@pytest.mark.parametrize("name, wf, plugin, pyproject, want", CASES, ids=[c[0] for c in CASES])
def test_reader(name, wf, plugin, pyproject, want):
    got, outs = m.read_workflow({m.WORKFLOW: wf}, plugin, CONFTEST, pyproject, REAL)
    assert got == want, [(o["pr_run_uploads"], o["pr_run_branch"], o["feature_push_branch"], o["why"]) for o in outs]

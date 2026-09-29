import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "signalflag-auth/scripts"))
import login


def test_notice_before_client(capsys):
    seen = []
    def fake():
        seen.append(capsys.readouterr().out)
    assert login.main(make_client=fake) == 0
    assert "URL" in seen[0]


def test_missing_sdk_exits_3(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "signalflag.sdk.auth", None)
    assert login.main() == 3
    assert "venv" in capsys.readouterr().err

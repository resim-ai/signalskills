import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "skills/signalflag-auth/scripts"))
import check_token as ct

NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def put(home: Path, d: str, body: str) -> None:
    (home / d).mkdir(parents=True, exist_ok=True)
    (home / d / "token.json").write_text(body)


def tok(delta: timedelta) -> str:
    return json.dumps({"access_token": "x", "expires_at": (NOW + delta).isoformat()})


def test_valid(tmp_path):
    put(tmp_path, ".signalflag", tok(timedelta(hours=5)))
    assert ct.status(tmp_path, NOW)[0] == 0


def test_inside_one_hour_margin_is_expired(tmp_path):
    put(tmp_path, ".signalflag", tok(timedelta(minutes=30)))
    assert ct.status(tmp_path, NOW)[0] == 1


def test_no_expires_at_is_expired(tmp_path):
    put(tmp_path, ".signalflag", json.dumps({"access_token": "x"}))
    assert ct.status(tmp_path, NOW)[0] == 1


def test_missing(tmp_path):
    code, msg = ct.status(tmp_path, NOW)
    assert code == 2 and ".signalflag/token.json" in msg


def test_corrupt_cache_is_missing(tmp_path):
    put(tmp_path, ".signalflag", '{"access_tok')
    assert ct.status(tmp_path, NOW)[0] == 2


def test_legacy_dir_used_when_only_it_exists(tmp_path):
    put(tmp_path, ".resim", tok(timedelta(hours=5)))
    assert ct.status(tmp_path, NOW)[0] == 0


def test_signalflag_dir_wins_over_legacy(tmp_path):
    put(tmp_path, ".resim", tok(timedelta(hours=5)))
    (tmp_path / ".signalflag").mkdir()
    assert ct.status(tmp_path, NOW)[0] == 2


def test_garbled_expires_at_is_expired(tmp_path):
    put(tmp_path, ".signalflag", json.dumps({"access_token": "x", "expires_at": "tomorrow"}))
    assert ct.status(tmp_path, NOW)[0] == 1


def test_naive_expires_at_read_as_utc(tmp_path):
    put(tmp_path, ".signalflag", json.dumps({"access_token": "x", "expires_at": (NOW + timedelta(hours=5)).replace(tzinfo=None).isoformat()}))
    assert ct.status(tmp_path, NOW)[0] == 0

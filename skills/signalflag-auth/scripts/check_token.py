"""Is there a usable SignalFlag token? Exit 0 valid, 1 expired, 2 missing. Stdlib only."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARGIN = timedelta(hours=1)  # the SDK refreshes inside this window


def cache_path(home: Path) -> Path:
    current, legacy = home / ".signalflag", home / ".resim"
    if not current.exists() and legacy.is_dir():
        return legacy / "token.json"
    return current / "token.json"


def status(home: Path, now: datetime) -> tuple[int, str]:
    path = cache_path(home)
    try:
        token = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return 2, f"missing: no token at {path}"
    expires = token.get("expires_at")
    try:
        at = datetime.fromisoformat(expires)
    except (TypeError, ValueError):
        return 1, f"expired: {path}"
    if now + MARGIN > (at if at.tzinfo else at.replace(tzinfo=timezone.utc)):
        return 1, f"expired: {path}"
    return 0, f"valid until {expires}"


if __name__ == "__main__":
    code, msg = status(Path.home(), datetime.now(timezone.utc))
    print(msg)
    sys.exit(code)

"""Records -> emits. Parses nothing."""
from __future__ import annotations

import json

from .events import detect
from .figures import scenario_map
from .records import TestRecord


def emit_test(t, rec: TestRecord, git_commit: str, git_dirty: bool) -> None:
    """Emit one test's rows onto `t` (a signalflag Test, or a bare Emitter for dry runs)."""
    ts = rec.start_ns
    t.emit("test_outcome", {"outcome": rec.outcome, "duration_s": float(rec.duration_s),
                            "message": rec.message[-4000:], "git_commit": git_commit,
                            "git_dirty": git_dirty}, ts)
    if rec.planner_result is not None:
        t.emit("planner_result", rec.planner_result, ts)
    t.emit("scenario_map_fig", {"raw_metric": json.dumps(scenario_map(rec))}, ts)
    for i, e in enumerate(detect(rec)):
        t.emit_event("planner_event", e, ts + i)

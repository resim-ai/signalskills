"""Longitudinal + lateral toy dynamics: ego follows a route while one actor does the scenario's maneuver."""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import numpy as np
import yaml

DT, MAX_DECEL = 0.1, 8.0
PASS = {"min_ttc_s": 1.5, "max_decel": 6.0, "route_completion": 0.95}

def simulate(sc: dict) -> dict:
    p = sc["params"]
    rng = np.random.default_rng(sc["seed"])
    ego_v, ego_x, gap = p["ego_speed"], 0.0, p["gap_m"]
    actor_x, actor_v = gap, p["actor_speed"]
    min_ttc, max_decel, collisions, steps = 99.0, 0.0, 0, int(sc["duration_s"] / DT)
    for k in range(steps):
        t = k * DT
        if p.get("event_t", 3.0) < t < p.get("event_t", 3.0) + 2.0:  # actor brakes for 2 s, then holds speed
            actor_v = max(0.0, actor_v - p.get("actor_brake", 0.0) * DT)
        rel_v = ego_v - actor_v
        dist = actor_x - ego_x - 4.5
        ttc = dist / rel_v if rel_v > 0.1 else 99.0
        min_ttc = min(min_ttc, ttc)
        want = 0.0 if ttc > p["planner_ttc"] else min(MAX_DECEL, rel_v ** 2 / max(2 * (dist - 6.0), 0.5))
        want += abs(rng.normal(0, 0.15))
        max_decel = max(max_decel, want)
        ego_v = max(0.0, ego_v - want * DT)
        ego_x += ego_v * DT
        actor_x += actor_v * DT
        if dist <= 0:
            collisions += 1
            break
    route = min(1.0, ego_x / max(p["route_m"], 1.0))
    return {"min_ttc_s": round(min(min_ttc, 99.0), 3), "max_decel": round(max_decel, 3),
            "collisions": collisions, "route_completion": round(route, 4)}

def run_all(scen_dir: Path, out: Path, filt: str = "") -> int:
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cases, failures = [], 0
    for f in sorted(scen_dir.rglob("*.yaml")):
        sc = yaml.safe_load(f.read_text())
        if filt not in sc["id"]:
            continue
        t0 = time.perf_counter()
        m = simulate(sc)
        ok = (m["collisions"] == 0 and m["min_ttc_s"] >= PASS["min_ttc_s"] and m["max_decel"] <= PASS["max_decel"]
              and m["route_completion"] >= PASS["route_completion"])
        res = {"scenario_id": sc["id"], "family": sc["family"], "pass": ok, **m}
        (out / f"{sc['id']}.json").write_text(json.dumps(res, indent=2) + "\n")
        cases.append((sc, res, time.perf_counter() - t0))
        failures += not ok
    lines = [f'<?xml version="1.0" encoding="utf-8"?>',
             f'<testsuites><testsuite name="simtest" tests="{len(cases)}" failures="{failures}" errors="0" timestamp="{started}">']
    for sc, res, dt in cases:
        lines.append(f'<testcase classname="simtest.{sc["family"]}" name="{sc["id"]}" time="{dt:.3f}">')
        if not res["pass"]:
            why = ", ".join(f"{k}={res[k]}" for k in ("collisions", "min_ttc_s", "max_decel", "route_completion"))
            lines.append(f'<failure message="{escape(why)}">{escape(json.dumps(res))}</failure>')
        lines.append("</testcase>")
    lines.append("</testsuite></testsuites>")
    (out / "junit.xml").write_text("\n".join(lines) + "\n")
    (out / "summary.json").write_text(json.dumps({
        "started_at": started, "commit": os.environ.get("GITHUB_SHA"), "ref": os.environ.get("GITHUB_REF_NAME"),
        "scenarios": len(cases), "passed": len(cases) - failures, "failed": failures}, indent=2) + "\n")
    print(f"{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0

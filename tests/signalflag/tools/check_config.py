"""Static checks of a config.resim.yml against the SignalFlag skill rules. Exit 1 on any violation."""
import sys
from pathlib import Path
import yaml

SYSTEM_TEMPLATES = {"line", "bar", "table", "scalar", "state_timeline", "histogram", "pie", "image", "video", "artifact"}
TOPIC_TYPES = {"boolean", "int", "float", "string", "status", "image", "video", "string[]", "metric[]"}
EVENT_FIELDS = {"name", "description", "status", "tags"}
MEDIA = {"image", "video"}
MAX_DESCRIPTION = 120


def _topic_violations(topics: dict) -> list[str]:
    out = []
    for name, t in topics.items():
        schema = t.get("schema", {})
        out += [f"topic {name}: unknown type {ty!r} for {col}" for col, ty in schema.items() if ty not in TOPIC_TYPES]
        if t.get("event") and not EVENT_FIELDS <= schema.keys():
            out.append(f"topic {name}: event schema needs {sorted(EVENT_FIELDS)}")
    return out


def _metric_violations(metrics: dict, templates_dir: Path) -> list[str]:
    out = []
    for name, m in metrics.items():
        if m.get("skip_if_no_data") is not True:
            out.append(f"metric {name}: skip_if_no_data must be true")
        d = str(m.get("description", ""))
        if not d or "\n" in d.strip() or len(d) > MAX_DESCRIPTION:
            out.append(f"metric {name}: description must be one line, <= {MAX_DESCRIPTION} chars")
        if m.get("template_type") == "custom":
            f = m.get("template_file")
            if not f or not (templates_dir / f).exists():
                out.append(f"metric {name}: custom template {f} not found in {templates_dir}")
        elif m.get("template") not in SYSTEM_TEMPLATES:
            out.append(f"metric {name}: unknown template {m.get('template')!r}")
        if m.get("template") == "scalar" and not m.get("units"):
            out.append(f"metric {name}: scalar needs units")
    return out


def _set_violations(sets: dict, metrics: dict) -> list[str]:
    out = []
    for sname, s in sets.items():
        names = s.get("metrics", [])
        out += [f"set {sname}: unknown metric {n}" for n in names if n not in metrics]
        test = [n for n in names if metrics.get(n, {}).get("type") == "test"]
        if test and not 5 <= len(test) <= 20:
            out.append(f"set {sname}: {len(test)} test metrics, want 5-20")
        media = [n for n in test if metrics[n].get("template") in MEDIA]
        if media and test[0] not in media:
            out.append(f"set {sname}: media metric {media[0]} must come first")
        for level in ("batch", "dashboard"):
            if sum(metrics.get(n, {}).get("type") == level for n in names) > 20:
                out.append(f"set {sname}: more than 20 {level} metrics")
    return out


def violations(path: Path) -> list[str]:
    cfg = yaml.safe_load(path.read_text())
    metrics = cfg.get("metrics", {})
    return (_topic_violations(cfg.get("topics", {}))
            + _metric_violations(metrics, path.parent / "templates")
            + _set_violations(cfg.get("metrics sets", {}), metrics))


if __name__ == "__main__":
    found = violations(Path(sys.argv[1]))
    print("\n".join(found) or "clean")
    sys.exit(1 if found else 0)

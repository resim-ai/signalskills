"""What each scenario run will report. Fields may still change."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class ScenarioMetrics:
    scenario: str
    reached_goal: bool
    time_to_goal_s: float
    min_obstacle_distance_m: float
    path_length_m: float
    collisions: int

def write_metrics(out_dir: Path, m: ScenarioMetrics) -> Path:
    path = out_dir / m.scenario / "metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(m), indent=2) + "\n")
    return path

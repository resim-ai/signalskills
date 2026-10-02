"""Run every scenario in the sim and write results/<scenario>/metrics.json."""
import argparse
from pathlib import Path
import yaml
from harness.metrics import ScenarioMetrics, write_metrics

def run_scenario(spec: dict) -> ScenarioMetrics:
    # TODO: launch the sim (gazebo headless), spawn the robot at spec["start"], send spec["goal"],
    # record /odom and /scan, compute the metrics.
    raise NotImplementedError("sim not wired up yet")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=Path("harness/scenarios"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    a = ap.parse_args()
    for f in sorted(a.scenarios.glob("*.yaml")):
        spec = yaml.safe_load(f.read_text())
        write_metrics(a.out, run_scenario(spec))

if __name__ == "__main__":
    main()

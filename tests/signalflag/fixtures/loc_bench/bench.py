"""Run the estimator on every sequence; write sequences/<seq>/estimate.txt and print ATE/RPE."""
from pathlib import Path
import numpy as np
from loc import estimator
from loc.metrics import ate_rmse, rpe_rmse
from loc.tum import read_tum, write_tum

SEQUENCES = Path(__file__).parent / "sequences"

def run_sequence(seq: Path) -> tuple[float, float]:
    gt = read_tum(seq / "groundtruth.txt")
    odom = np.loadtxt(seq / "odometry.csv", delimiter=",", skiprows=1)
    scans = np.loadtxt(seq / "scan_match.csv", delimiter=",", skiprows=1)
    x, y, yaw = estimator.run(odom, scans, gt[:, 0])
    write_tum(seq / "estimate.txt", gt[:, 0], x, y, yaw)
    est = read_tum(seq / "estimate.txt")
    return ate_rmse(gt, est), rpe_rmse(gt, est)

if __name__ == "__main__":
    print(f"{'sequence':16s} {'ATE (m)':>8s} {'RPE (m)':>8s}")
    for seq in sorted(p for p in SEQUENCES.iterdir() if p.is_dir()):
        ate, rpe = run_sequence(seq)
        print(f"{seq.name:16s} {ate:8.3f} {rpe:8.3f}")

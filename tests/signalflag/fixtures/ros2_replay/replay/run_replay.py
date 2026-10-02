"""Play every scenario bag through the running perception stack and record what it publishes.

Runs inside the `replay` container. For each scenarios/<name>.mcap writes
  outputs/<name>/output.mcap   (/perception/detections, /perception/tracks)
  outputs/<name>/replay.log
"""
import argparse, shutil, signal, subprocess, time
from pathlib import Path

TOPICS = ["/perception/detections", "/perception/tracks"]

def replay(bag: Path, out_root: Path) -> None:
    out = out_root / bag.stem
    shutil.rmtree(out, ignore_errors=True)
    log = [f"[replay] scenario={bag.stem} bag={bag} rate=1.0 clock=on"]
    rec = subprocess.Popen(["ros2", "bag", "record", "-s", "mcap", "--use-sim-time", "-o", str(out / "rec"), *TOPICS])
    time.sleep(2.0)  # let the recorder discover the topics
    play = subprocess.run(["ros2", "bag", "play", str(bag), "--clock", "--rate", "1.0"])
    time.sleep(1.0)
    rec.send_signal(signal.SIGINT)
    rec.wait(timeout=30)
    (out / "rec" / "rec_0.mcap").rename(out / "output.mcap")
    shutil.rmtree(out / "rec")
    log.append(f"[replay] recorded {' '.join(TOPICS)} -> {out / 'output.mcap'}")
    log.append(f"[replay] done: exit {play.returncode}")
    (out / "replay.log").write_text("\n".join(log) + "\n")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=Path("scenarios"))
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    a = ap.parse_args()
    for bag in sorted(a.scenarios.glob("*.mcap")):
        replay(bag, a.out)

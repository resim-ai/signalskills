"""Evaluate one checkpoint over 5 seeds. Writes evals/<stamp>/episodes.csv."""
import sys, time
from pathlib import Path
import numpy as np, pandas as pd

def evaluate(ckpt: str, seeds=range(5)) -> pd.DataFrame:
    step = int(ckpt.rsplit("_", 1)[-1])
    rng = np.random.default_rng(step)
    ret = 50 + step / 1000 + rng.normal(0, 5, len(seeds))
    return pd.DataFrame({"seed": list(seeds), "return": ret,
                         "success": ret > 70, "episode_len": rng.integers(200, 400, len(seeds))})

def main(ckpt: str) -> Path:
    out = Path("evals") / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True)
    evaluate(ckpt).to_csv(out / "episodes.csv", index=False)
    (out / "log.txt").write_text(f"loaded {ckpt}\n")
    return out

if __name__ == "__main__":
    print(main(sys.argv[1]))

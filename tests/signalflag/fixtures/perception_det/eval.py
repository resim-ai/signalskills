"""Evaluate one checkpoint on the val splits. Writes eval/<epoch>/metrics_<split>.json."""
import argparse, json, re
from pathlib import Path
from det3d_eval.scoring import SPLITS, evaluate_split, load_checkpoint

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--splits", nargs="+", default=list(SPLITS), choices=list(SPLITS))
    ap.add_argument("--out", type=Path, default=Path("eval"))
    a = ap.parse_args()
    epoch = int(re.search(r"ckpt_(\d+)\.pth$", a.ckpt).group(1))
    ckpt = load_checkpoint(a.ckpt)
    out = a.out / str(epoch)
    out.mkdir(parents=True, exist_ok=True)
    for split in a.splits:
        m = {"split": split, "epoch": epoch, "checkpoint": a.ckpt, **evaluate_split(ckpt, split)}
        (out / f"metrics_{split}.json").write_text(json.dumps(m, indent=2) + "\n")
        print(f"epoch {epoch} {split:6s} mAP {m['mean_ap']:.4f} NDS {m['nd_score']:.4f}")

if __name__ == "__main__":
    main()

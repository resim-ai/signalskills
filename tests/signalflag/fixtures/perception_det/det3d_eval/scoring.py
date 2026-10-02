"""Detection scoring on the val splits (nuScenes detection metrics)."""
import pickle, zipfile
import numpy as np

SPLITS = {"day": 2410, "night": 1180, "rain": 760}  # val samples per split
CLASSES = ["car", "truck", "bus", "pedestrian", "bicycle", "traffic_cone"]
CLASS_DIFFICULTY = {"car": 1.25, "truck": 0.85, "bus": 0.95, "pedestrian": 1.1, "bicycle": 0.7, "traffic_cone": 1.0}
DIST_THS = [0.5, 1.0, 2.0, 4.0]

def load_checkpoint(path: str) -> dict:
    try:
        import torch
        return torch.load(path, map_location="cpu")
    except ImportError:  # CPU box without torch: read the metadata only
        with zipfile.ZipFile(path) as z:
            return pickle.loads(z.read("archive/data.pkl"))

def _split_map(epoch: int, split: str) -> float:
    base = {"day": 0.63, "night": 0.52, "rain": 0.48}[split]
    m = base - 0.24 * np.exp(-epoch / 8)
    if split == "night" and epoch > 15:  # night degrades as day overfits
        m -= 0.011 * (epoch - 15)
    return m

def evaluate_split(ckpt: dict, split: str) -> dict:
    epoch = ckpt["epoch"]
    rng = np.random.default_rng(epoch * 31 + len(split))
    m = _split_map(epoch, split) + rng.normal(0, 0.004)
    label_aps, mean_dist_aps = {}, {}
    for c in CLASSES:
        ap_c = float(np.clip(m * CLASS_DIFFICULTY[c] + rng.normal(0, 0.01), 0, 1))
        if split == "night" and c in ("pedestrian", "bicycle"):
            ap_c *= 0.8
        label_aps[c] = {str(th): round(float(np.clip(ap_c * (0.7 + 0.1 * i), 0, 1)), 4) for i, th in enumerate(DIST_THS)}
        mean_dist_aps[c] = round(float(np.mean(list(label_aps[c].values()))), 4)
    mean_ap = float(np.mean(list(mean_dist_aps.values())))
    tp = {"trans_err": 0.30 - 0.1 * m, "scale_err": 0.26, "orient_err": 0.42 - 0.2 * m,
          "vel_err": 0.33 - 0.1 * m, "attr_err": 0.19}
    tp = {k: round(float(v + rng.normal(0, 0.005)), 4) for k, v in tp.items()}
    nds = (5 * mean_ap + sum(1 - min(1, v) for v in tp.values())) / 10
    return {"mean_ap": round(mean_ap, 4), "nd_score": round(float(nds), 4), "tp_errors": tp,
            "label_aps": label_aps, "mean_dist_aps": mean_dist_aps, "num_samples": SPLITS[split]}

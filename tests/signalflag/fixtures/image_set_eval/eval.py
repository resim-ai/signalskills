"""Score detector predictions against labels. Prints AP@0.5 per class, mAP, and P/R at a score threshold."""
import argparse, csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLASSES = ["car", "pedestrian", "truck", "forklift"]


def iou(a, b) -> float:
    """IoU of two [x, y, w, h] boxes."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / (a[2] * a[3] + b[2] * b[3] - i) if i else 0.0


def load_meta() -> dict:
    with open(ROOT / "meta.csv") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def load(kind: str, image_id: str, model: str = "") -> dict:
    p = ROOT / "labels" / f"{image_id}.json" if kind == "labels" else ROOT / "predictions" / model / f"{image_id}.json"
    return json.loads(p.read_text())


def match_image(gt: list, preds: list, iou_thr: float = 0.5):
    """Greedy, highest score first, same class. Returns (pred_tp flags, gt_matched flags)."""
    order = sorted(range(len(preds)), key=lambda i: -preds[i]["score"])
    used, tp = set(), [False] * len(preds)
    for pi in order:
        best, bi = iou_thr, None
        for gi, g in enumerate(gt):
            if gi in used or g["category"] != preds[pi]["category"]:
                continue
            s = iou(g["bbox"], preds[pi]["bbox"])
            if s >= best:
                best, bi = s, gi
        if bi is not None:
            used.add(bi)
            tp[pi] = True
    return tp, [gi in used for gi in range(len(gt))]


def average_precision(scored: list, n_gt: int) -> float:
    """scored: [(score, is_tp)]. All-point interpolated AP."""
    if not n_gt:
        return float("nan")
    tp = fp = 0
    pts = []
    for _, t in sorted(scored, key=lambda x: -x[0]):
        tp, fp = tp + t, fp + (not t)
        pts.append((tp / n_gt, tp / (tp + fp)))
    ap, prev_r = 0.0, 0.0
    for i, (r, _) in enumerate(pts):
        p = max(q for _, q in pts[i:])
        ap += (r - prev_r) * p
        prev_r = r
    return ap


def evaluate(model: str, score_thr: float = 0.5, iou_thr: float = 0.5) -> dict:
    scored = {c: [] for c in CLASSES}
    n_gt = {c: 0 for c in CLASSES}
    tp = {c: 0 for c in CLASSES}
    fp = {c: 0 for c in CLASSES}
    for image_id in load_meta():
        gt = load("labels", image_id)["annotations"]
        preds = load("predictions", image_id, model)["detections"]
        flags, _ = match_image(gt, preds, iou_thr)
        for g in gt:
            n_gt[g["category"]] += 1
        for p, t in zip(preds, flags):
            scored[p["category"]].append((p["score"], t))
        # thresholded P/R: re-match only the kept predictions
        kept = [p for p in preds if p["score"] >= score_thr]
        kflags, _ = match_image(gt, kept, iou_thr)
        for p, t in zip(kept, kflags):
            (tp if t else fp)[p["category"]] += 1
    ap = {c: average_precision(scored[c], n_gt[c]) for c in CLASSES}
    return {"model": model, "mAP50": sum(ap.values()) / len(ap), "AP50": ap, "n_gt": n_gt,
            "precision": {c: tp[c] / max(1, tp[c] + fp[c]) for c in CLASSES},
            "recall": {c: tp[c] / max(1, n_gt[c]) for c in CLASSES},
            "overall_precision": sum(tp.values()) / max(1, sum(tp.values()) + sum(fp.values())),
            "overall_recall": sum(tp.values()) / max(1, sum(n_gt.values()))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", help="model version under predictions/ (repeatable); default: all")
    ap.add_argument("--score-thr", type=float, default=0.5)
    ap.add_argument("--iou", type=float, default=0.5)
    a = ap.parse_args()
    models = a.model or sorted(p.name for p in (ROOT / "predictions").iterdir() if p.is_dir())
    for m in models:
        r = evaluate(m, a.score_thr, a.iou)
        print(f"{m}: mAP@{a.iou:g} {r['mAP50']:.3f}  P {r['overall_precision']:.3f}  R {r['overall_recall']:.3f}"
              f"  (score >= {a.score_thr:g}, {sum(r['n_gt'].values())} labeled objects)")
        for c in CLASSES:
            print(f"  {c:10s} AP {r['AP50'][c]:.3f}  P {r['precision'][c]:.3f}  R {r['recall'][c]:.3f}  n={r['n_gt'][c]}")

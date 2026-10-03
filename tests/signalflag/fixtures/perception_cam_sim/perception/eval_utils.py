"""Helpers for scoring a replay against labels/<scenario>.jsonl."""
import json
from pathlib import Path


def iou(a: dict, b: dict) -> float:
    """IoU of two {x_min, y_min, x_max, y_max} boxes."""
    ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    inter = ix * iy
    area = lambda r: (r["x_max"] - r["x_min"]) * (r["y_max"] - r["y_min"])
    return inter / (area(a) + area(b) - inter) if inter > 0 else 0.0


def match(gt: list, pred: list, iou_threshold: float = 0.5, class_aware: bool = True):
    """Greedy one-to-one matching, highest IoU first.
    gt / pred: lists of dicts with "bbox_2d" (and "class").
    Returns (matches [(gt_index, pred_index, iou)], unmatched_gt [index], unmatched_pred [index])."""
    pairs = sorted(((iou(g["bbox_2d"], p["bbox_2d"]), gi, pi) for gi, g in enumerate(gt) for pi, p in enumerate(pred)
                    if not class_aware or g["class"] == p["class"]), reverse=True)
    used_g, used_p, matches = set(), set(), []
    for s, gi, pi in pairs:
        if s < iou_threshold or gi in used_g or pi in used_p:
            continue
        used_g.add(gi), used_p.add(pi)
        matches.append((gi, pi, s))
    return (matches, [i for i in range(len(gt)) if i not in used_g], [i for i in range(len(pred)) if i not in used_p])


def load_labels(path) -> list:
    """labels/<scenario>.jsonl -> list of {"frame", "stamp", "objects"} in frame order."""
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def stamp_ns(stamp: dict) -> int:
    return int(stamp["sec"]) * 1_000_000_000 + int(stamp["nanosec"])

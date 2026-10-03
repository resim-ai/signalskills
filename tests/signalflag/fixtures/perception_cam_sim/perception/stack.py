"""CPU stand-in for the acme camera perception stack (acme/perception image): detector + tracker.

The release stack runs a TensorRT detector on the full-resolution camera. This module reproduces its interface and
its measured behaviour (bench calibration of the 2026.09 model) so the replay harness runs anywhere: the detector
is a sensor model over the objects in view, plus the image-dependent parts (scene brightness, the derain
pre-filter, bright clutter).
"""
import numpy as np

CLASSES = ("car", "pedestrian", "cyclist", "truck")
PREVIEW_SCALE = 20  # preview px -> sensor px (96x64 -> 1920x1280)
SIZES = {"car": (1.8, 1.5), "truck": (2.5, 3.5), "pedestrian": (0.6, 1.75), "cyclist": (0.7, 1.7)}
FOCAL_PX, HORIZON_PX, CAMERA_HEIGHT_M = 1600.0, 560.0, 1.6

DETECTOR = {
    "score_threshold": 0.3,
    "recall": {"car": 0.97, "truck": 0.97, "pedestrian": 0.96, "cyclist": 0.95},
    "full_recall_range_m": 38.0, "range_falloff_m": 7.0,
    "low_light_luminance": 60.0, "low_light_recall": {"car": 0.97, "truck": 0.97, "pedestrian": 0.22, "cyclist": 0.5},
    "occluded_fraction": 0.6, "occluded_recall": 0.2, "nms_iou": 0.3,
    "box_jitter": 0.04, "range_jitter": 0.03,
}
TRACKER = {"iou_gate": 0.3, "min_hits": 3, "max_misses": 4, "publish_max_misses": 1}
LATENCY = {"base_ms": 38.0, "per_detection_ms": 2.2, "jitter_ms": 3.0,
           "derain_trigger_px": 90, "derain_ms": 70.0, "budget_ms": 100.0}


def iou(a: dict, b: dict) -> float:
    ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    inter = ix * iy
    area = lambda r: (r["x_max"] - r["x_min"]) * (r["y_max"] - r["y_min"])
    return inter / (area(a) + area(b) - inter) if inter > 0 else 0.0


def _covered(a: dict, b: dict) -> float:
    """Fraction of box a covered by box b."""
    ix = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    iy = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    return ix * iy / max(1e-6, (a["x_max"] - a["x_min"]) * (a["y_max"] - a["y_min"]))


def _r(x, n=1):
    return round(float(x), n)


class Tracker:
    """Greedy IoU tracker (constant-position prediction). Confirmed after min_hits consecutive hits; published while
        updated this frame or coasting through one missed frame."""

    def __init__(self):
        self.tracks, self.next_id = [], 1

    def update(self, dets: list) -> list:
        pairs = sorted(((iou(t["bbox_2d"], d["bbox_2d"]), ti, di) for ti, t in enumerate(self.tracks)
                        for di, d in enumerate(dets) if t["class"] == d["class"]), reverse=True)
        used_t, used_d = set(), set()
        for s, ti, di in pairs:
            if s < TRACKER["iou_gate"] or ti in used_t or di in used_d:
                continue
            used_t.add(ti), used_d.add(di)
            t, d = self.tracks[ti], dets[di]
            t.update(bbox_2d=d["bbox_2d"], range_m=d["range_m"], hits=t["hits"] + 1, misses=0)
        for ti, t in enumerate(self.tracks):
            t["age"] += 1
            if ti not in used_t:
                t["misses"] += 1
        self.tracks = [t for t in self.tracks if t["misses"] == 0 or  # tentative tracks die on their first miss
                       (t["hits"] >= TRACKER["min_hits"] and t["misses"] <= TRACKER["max_misses"])]
        for di, d in enumerate(dets):
            if di not in used_d:
                self.tracks.append({"track_id": self.next_id, "class": d["class"], "bbox_2d": d["bbox_2d"],
                                    "range_m": d["range_m"], "age": 0, "hits": 1, "misses": 0})
                self.next_id += 1
        return [{k: t[k] for k in ("track_id", "class", "bbox_2d", "range_m", "age")} for t in self.tracks
                if t["hits"] >= TRACKER["min_hits"] and t["misses"] <= TRACKER["publish_max_misses"]]


class PerceptionStack:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)
        self.tracker = Tracker()

    def _detect(self, objects: list, low_light: bool) -> list:
        c, dets = DETECTOR, []
        for o in sorted(objects, key=lambda o: o["range_m"]):
            u = self.rng.random(4)
            p = (c["low_light_recall"] if low_light else c["recall"])[o["class"]]
            if o["range_m"] > c["full_recall_range_m"]:
                p *= np.exp(-(o["range_m"] - c["full_recall_range_m"]) / c["range_falloff_m"])
            if any(_covered(o["bbox_2d"], n["bbox_2d"]) > c["occluded_fraction"]
                   for n in objects if n["range_m"] < o["range_m"]):
                p *= c["occluded_recall"]
            if u[0] >= p:
                continue
            b = o["bbox_2d"]
            w, h = b["x_max"] - b["x_min"], b["y_max"] - b["y_min"]
            j = self.rng.normal(0, c["box_jitter"], 4)
            box = {"x_min": _r(b["x_min"] + j[0] * w), "y_min": _r(b["y_min"] + j[1] * h),
                   "x_max": _r(b["x_max"] + j[2] * w), "y_max": _r(b["y_max"] + j[3] * h)}
            score = float(np.clip(0.82 + 0.06 * self.rng.standard_normal(), 0.31, 0.99))
            dets.append({"class": o["class"], "score": _r(score, 3), "bbox_2d": box,
                         "range_m": _r(o["range_m"] * (1 + c["range_jitter"] * (2 * u[1] - 1)), 2)})
        return dets

    @staticmethod
    def _nms(dets: list) -> list:
        """Class-wise non-maximum suppression, highest score first."""
        keep = []
        for d in sorted(dets, key=lambda d: -d["score"]):
            if all(k["class"] != d["class"] or iou(k["bbox_2d"], d["bbox_2d"]) <= DETECTOR["nms_iou"] for k in keep):
                keep.append(d)
        return keep

    def _clutter(self, rgb: np.ndarray) -> list:
        """Saturated blobs (glare, reflections) fire the pedestrian head."""
        ys, xs = np.nonzero(rgb.min(axis=2) > 225)
        if len(xs) < 4:
            return []
        s = PREVIEW_SCALE
        y2 = (ys.max() + 1) * s
        h = y2 - ys.min() * s
        cx = (xs.min() + xs.max() + 1) / 2 * s
        rng_m = FOCAL_PX * CAMERA_HEIGHT_M / max(1.0, y2 - HORIZON_PX)
        return [{"class": "pedestrian", "score": _r(0.55 + 0.1 * self.rng.random(), 3),
                 "bbox_2d": {"x_min": _r(cx - 0.18 * h), "y_min": _r(y2 - h), "x_max": _r(cx + 0.18 * h), "y_max": _r(y2)},
                 "range_m": _r(rng_m, 2)}]

    def step(self, image, objects: list) -> dict:
        """image: PIL preview of the camera frame; objects: what is in view (label format)."""
        rgb = np.asarray(image.convert("RGB")).astype(np.int16)
        lum = rgb @ np.array([299, 587, 114]) / 1000
        low_light = lum.mean() < DETECTOR["low_light_luminance"]
        streak_px = int(((lum[:, 1:-1] - np.maximum(lum[:, :-2], lum[:, 2:])) > 20).sum())  # thin vertical streaks
        derain = streak_px > LATENCY["derain_trigger_px"]
        dets = self._detect(objects, low_light) + self._clutter(rgb)
        dets = self._nms([d for d in dets if d["score"] >= DETECTOR["score_threshold"]])
        tracks = self.tracker.update(dets)
        ms = LATENCY["base_ms"] + LATENCY["per_detection_ms"] * len(dets) + LATENCY["jitter_ms"] * self.rng.standard_normal()
        if derain:
            ms += LATENCY["derain_ms"] + 8.0 * self.rng.standard_normal()
        return {"detections": dets, "tracks": tracks, "e2e_ms": round(float(ms), 2), "derain": bool(derain),
                "low_light": bool(low_light)}

# det-v4 offline eval

Offline evaluation of the acme 2D detector on the frozen photo set `acme-eval-2026.09` (not a replay: one
labeled photo per file).

```
python eval.py                         # every model under predictions/
python eval.py --model det-v4.2 --score-thr 0.5
```

- `images/<source>/<id>.jpg`: 96x64 previews (the full-res set stays in the bucket). Sources: dashcam_a,
  dashcam_b, warehouse_cam.
- `meta.csv`: `id, source, condition (day/night/fog), timestamp` per image.
- `labels/<id>.json`: COCO-style ground truth, `bbox` = `[x, y, w, h]` in full-res pixels (960x640).
  Classes: car, pedestrian, truck, forklift.
- `predictions/<model_version>/<id>.json`: detector output for the same image (`bbox`, `category`, `score`),
  exported at score >= 0.05. `predictions/<model_version>/manifest.json` says where it came from.
- `eval.py`: matches predictions to labels (IoU >= 0.5, greedy by score) and prints AP per class, mAP and
  precision/recall at a score threshold.

Release question: ship det-v4.2 (retrained with the new warehouse data) to replace det-v4.1?

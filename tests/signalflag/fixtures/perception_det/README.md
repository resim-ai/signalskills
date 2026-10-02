# centerpoint-v3

3D detector training + evaluation on the internal val splits (`day`, `night`, `rain`).

Training (on the cluster) saves `runs/centerpoint_v3/ckpt_<epoch>.pth` every 5 epochs. Evaluate one:

```
python eval.py --ckpt runs/centerpoint_v3/ckpt_25.pth
```

Writes `eval/<epoch>/metrics_<split>.json` per split (nuScenes-style: mAP, NDS, TP errors, per-class AP).

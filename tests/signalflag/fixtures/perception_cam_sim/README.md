# yard-perception replay

Camera perception (2D detection + tracking) for the acme autonomous yard tractor. Recorded front-camera drives are
replayed through the perception stack and everything it publishes is recorded.

```
python replay/run_replay.py --scenario day_parking_lot   # one scenario
python replay/run_replay.py                              # all of them
docker compose run --rm replay                           # same thing, in the release image
```

- `scenarios/<name>.yaml`: what each drive is (site, lighting, weather) and where its recording + labels live.
- `recordings/<name>.mcap`: the recorded input, `/camera/front/image` (JPEG) at 10 Hz, 8 s per drive.
- `labels/<name>.jsonl`: ground truth from the labeling vendor, one line per camera frame:
  `{"frame", "stamp", "objects": [{"object_id", "class", "bbox_2d", "range_m"}]}`.
- `outputs/<name>/replay.mcap`: what the stack published during the last replay (overwritten each run):
  `/camera/front/image` (annotated preview), `/perception/detections`, `/perception/tracks`,
  `/perception/latency`, `/diagnostics`. Also `camera.mp4` (annotated preview) and `replay.gif` (every 4th frame).
- `perception/stack.py`: CPU stand-in for the stack in `acme/perception` (so the harness runs on a laptop).
- `perception/eval_utils.py`: IoU + greedy matcher for scoring against the labels.

Classes: car, pedestrian, cyclist, truck. `bbox_2d` is `{x_min, y_min, x_max, y_max}` in sensor pixels (1920x1280);
the JPEGs are 96x64 previews (sensor / 20). `range_m` is distance from the camera. Track `age` is in frames.
End-to-end latency budget (camera stamp to tracks out): 100 ms.

TODO: score replays against the labels (nobody has wired this up yet).

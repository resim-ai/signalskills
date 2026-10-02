# Detector photo-set evaluation — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- 240 labeled photos in `images/<source>/<id>.jpg` from dashcam_a, dashcam_b and warehouse_cam; per-image `meta.csv` (source, condition day/night/fog, timestamp); labels in `labels/<id>.json` (COCO-style boxes: car, pedestrian, truck, forklift).
- Predictions per model version in `predictions/<model_version>/<id>.json`; two versions on disk: det-v4.1, det-v4.2. New versions arrive every week or two.
- `eval.py` matches predictions to labels (IoU 0.5) and prints overall and per-class AP / precision / recall; it doesn't slice by condition, size or source.

## Intent
Metrics-first, experiment tracking. The perception ML engineer opens SignalFlag to decide whether a new detector version is better than the last one, where it's better or worse (class, condition, object size, source), and which images to look at. Not a CI gate.

## Control
Mode: B (guided). Metrics and events: partial — agent proposes, user picks.

## Mapping
In the user's words: each model version evaluated on the photo set is one run; versions are compared with each other.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `detector-photo-eval` (confirmed by user: yes)
- Batch is: one model version evaluated on the whole set.
- Test is: one image, named by its id, e.g. `da_0039` (confirmed by user: yes)
- Version is: the model version, e.g. `det-v4.2` (confirmed by user: yes)

## Integration
- Form: script — `ingest_photo_eval.py --model <version>` over `predictions/<version>/`, reusing `eval.py`'s matcher.
- structure-runs needed: no.
- Environment: `.venv-signalflag/`, git-ignored.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

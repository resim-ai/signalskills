# Delivery QA — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- No harness or runner. Each customer delivery is a folder `deliveries/<delivery_id>/`:
  - `videos/*.mp4`: egocentric head-camera clips, one task per clip. These are proxy-resolution copies; full-res stays in the bucket.
  - `annotations.json`: `delivery_id`, `client`, and per video `file`, `duration_s`, `fps`, `task`, `hand_visibility` segments (`start_s`, `end_s`, `left`, `right`), `collector_id`, `device`.
- Present: `DLV-2026-0915` (150 clips, ~1.2 MB) and `DLV-2026-0929` (152 clips, ~1.3 MB). Both are for `client-07`. 5 tasks (stack_cups, wipe_table, fold_towel, pour_water, open_drawer), 2 devices (headcam-v3/v4), all annotated at 15 fps, 0.9–15.4 s long. In both deliveries, the annotation file entries and the clip files match one-to-one.
- Frequency: a new delivery folder roughly every two weeks.
- Today's QA: someone skims a sample of clips before shipping. Nothing is recorded. The goal is to check every clip.
- Tooling on the machine: `ffprobe`/`ffmpeg` are available. There is no OpenCV.

## Intent
- Question: "Is this delivery fit to ship? If not, which clips are bad and why?" A second question: "Is delivery quality drifting compared with earlier deliveries?"
- Asked by whoever ships the delivery. It is a **gate**: a failing check should stop the ship or flag clips to pull.
- **Metrics-first.** The checks are known: the file decodes, the actual video matches the annotations, and the hand-visibility annotations are complete and sane.

## Control
- Mode: **A** (agent decides). The user fixed the project and branch.
- Metrics and events: **agent-led**. Thresholds are not decided yet. The agent picks sensible starting values and marks them as provisional for the user to tune.

## Mapping
In their words: each delivery gets one QA pass, and every clip in it gets checked.
- Project: `acme-robotics` (confirmed by user: yes)
- Branch: `delivery-qa` (confirmed by user: yes)
- Batch is: one QA pass over one delivery folder (`deliveries/<delivery_id>/`). Re-running QA on the same delivery creates a new batch with the same version.
- Test is: one clip, named by the file stem (`ego_10000`) (chosen by agent — the gate question is "which clips fail", so each clip gets its own pass/fail and status. Clip names are unique per delivery and don't repeat across deliveries, so cross-delivery comparison happens at batch level on the branch dashboard, not test-to-test.)
- Version is: the `delivery_id` (`DLV-2026-0929`) (chosen by agent — it is what separates one delivery from the next, and it sorts by date.)
- Batch metadata: `client`, clip count, and the QA script's git commit.

## Integration
- Form: **script**. There are loose artifacts and no harness, so a QA script runs over `deliveries/<delivery_id>/` and is re-run for each new delivery (`python qa/ingest.py deliveries/DLV-2026-0929`).
- structure-runs needed: **no**. Each folder already records the delivery id, client and per-clip annotations; nothing ingest needs is missing.
- Environment: the repo has no Python project, so the script gets its own venv at `qa/.venv`. It uses `ffprobe` from the system for the video checks.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

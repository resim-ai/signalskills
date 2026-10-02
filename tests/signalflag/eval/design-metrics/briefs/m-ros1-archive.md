# Test-track ROS1 bags — SignalFlag test brief

Status: approved by user (onboarding).

One brief per test type or modality. Each skill fills its own section; leave the others as `_pending: <skill>_`.

## Current state
- Archive of ROS1 (Noetic) bags from the test track, 2022 to 2025: 40 bags, listed in `bags/INDEX.csv`
  (bag, recorded_utc, duration_s, size_bytes, location, topics).
- 4 bags are local in `bags/`. They were trimmed with `rosbag filter` to `/vehicle/pose`, `/vehicle/speed`, and
  `/perception/objects` (`track_perception_msgs/ObjectArray`). Each is ~20 s and ~85 KB, ROSBAG V2.0 with one chunk.
- 36 bags are full recordings (also `/velodyne_points`, `/camera/front/image_raw/compressed`, `/tf`) in
  `s3://acme-track-archive/bags/<year>/`. Each is 1,333–6,444 s and 12–58 GB, **~1.3 TB in total**. `scripts/fetch_bags.sh`
  is the existing way to download them (`aws s3 sync`, whole files).
- No harness or runner. This is a closed archive, with no new recordings since 2025. ROS is not installed anywhere,
  so bags must be read with a pure-Python reader (e.g. `rosbags`). Bags embed their message definitions, so the
  custom `track_perception_msgs` type doesn't need its package.
- Not recorded beyond INDEX.csv: vehicle/software version, driver, weather, or what each run was for.

## Intent
- Data-first exploration of the historical archive: the vehicle and perception data from four years on the track, side
  by side, with a few summary metrics per run (speed, distance, perception object counts). Exploration, not a gate.
- Chosen by agent: there's no harness or asserted thresholds to turn into checks, and the data is all logged and
  never asserted on (see `mapping.md`).

## Control
- Mode: A (agent decides). The user's single go comes after the Metrics plan.
- Metrics and events: agent-led.

## Mapping
- Project: `acme-robotics` (given by user)
- Branch: `track-archive` (confirmed by user: yes)
- Batch is: one bag (one track session/run), so that a dashboard on the branch trends across 2022 to 2025.
- Test is: `test-track`, one test per batch, the same name in every batch so that all runs compare (chosen by agent —
  every bag is a session on the same track with no scenario split, and matching names are what make batches
  comparable).
- Version is: the bag stem, e.g. `track_2024-03-08_run01`, which is unique per bag and sorts chronologically. Batch
  metadata also gets `recorded_utc` from INDEX.csv (chosen by agent — there's no software version or commit recorded).

## Integration
- Form: one-off script (`scripts/ingest_bags.py`) over `bags/*.bag` plus `INDEX.csv`. It can be re-run per bag as more
  are fetched and skips bags already pushed. It's a closed archive, so no hook is needed.
- structure-runs needed: no. INDEX.csv plus the bag stem give everything that ingest needs.
- Environment: own venv at `.venv-signalflag/` (git-ignored), with the SignalFlag SDK and `rosbags`.
- Open item: **getting the 36 S3 bags.** Only the 3 small topics are needed, but `fetch_bags.sh` downloads whole files
  (~1.3 TB including lidar/camera). Options to settle at the go: (a) ingest the 4 local bags first, then fetch the rest
  one at a time to temp storage, extract the 3 topics, and delete the file, or (b) read just the needed chunks using S3
  range requests. AWS credentials and access to the archive are unverified.

## Data profile
_pending: signalflag-design-metrics_

## Metrics plan
_pending: signalflag-design-metrics_

## Config
_pending: signalflag-compose-metrics_

## Verification
_pending: signalflag-verify_

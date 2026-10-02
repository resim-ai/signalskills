# Templates and starter metrics

## Which template answers which question

| Question | Template |
|---|---|
| How did X change during the run | line |
| How do categories/tests/builds compare | bar |
| Ranking, many values per row | table |
| Headline number | scalar |
| Which mode, when | state_timeline |
| How is X spread | histogram |
| Share of one whole (≤ 6 slices) | pie |

# Starter metrics by domain

Propose a row only when the data profile has the fields in "Needs". **(py)** = SQL can't compute it: compute in Python at ingest, emit the value and its series.

## Navigation / path following
| Metric | Needs | Level | Template |
|---|---|---|---|
| Replay of the run | replay GIF → `image`; MP4 → `video` | test | image / video by file |
| Cross-track error over time | pose + reference path, timestamps | test | line |
| RMS / peak cross-track | same | test | table |
| Terminal distance, and margin to tolerance | final pose, goal, tolerance | test | table + status |
| Time to goal vs planned | start/end stamps, planned duration | test | scalar |
| Command saturation share | commanded vs limits | test | scalar |
| Mode over time | a mode/state field | test | state_timeline |
| Terminal distance by route | per-test terminal distance | batch | bar |
| Cross-track spread across routes | per-test cross-track | batch | histogram |
| Terminal margin over builds | margin + build_version | dashboard | line |

## Manipulation
| Metric | Needs | Level | Template |
|---|---|---|---|
| Replay | camera (GIF → `image`, MP4 → `video`) | test | image / video by file |
| Stage reached, and time to each stage | stage events with timestamps | test | bar |
| Success rate by build | per-test success | dashboard | bar |
| Grasp attempts per success | attempt events | batch | histogram |

## Perception
| Metric | Needs | Level | Template |
|---|---|---|---|
| Camera with detections/tracks overlaid (scrub: MP4) | camera + outputs | test | video |
| Precision / recall per class, with margin (py: IoU matching) | truth + detections | test | table + status |
| Recall by range bin (and by size / occlusion) (py) | truth range + matches | test | bar |
| Recall over time / per frame (py) | same, stamps | test | line |
| Missed objects and false positives: one event per object/burst with its frame (py) | same | test | event + image |
| Tracking: ID switches, fragmentations, track flicker (py) | tracks + truth ids | test | table + status |
| Track lifetime | tracks | test | histogram |
| End-to-end latency vs budget, p50/p95, and over time | input and output stamps | test | table + status, line |
| Dropped frames / output cadence | output stamps | test | line |
| Stack health (diagnostics level over time) | diagnostics | test | state_timeline |
| No labels yet: count per class over time, box jitter, flicker rate | detections/tracks | test | line, table |
| Recall / precision per class by scenario (day vs night, weather) | per-test values | batch | bar |
| Per-class recall over builds/checkpoints | per-test values + version | dashboard | line |

## RL training and evaluation
| Metric | Needs | Level | Template |
|---|---|---|---|
| Return per episode/seed | per-episode return | test | table |
| Mean return with spread (sd, min, max) | returns per checkpoint | batch | table |
| Success rate (and its definition) | success flag or its rule | batch | scalar |
| Return over step, with min–max band | step as version | dashboard | line |
| Checkpoint leaderboard | per-batch mean return | dashboard | table |

## Sim health
| Metric | Needs | Level | Template |
|---|---|---|---|
| Real-time factor | sim and wall clock | test | line |
| Dropped / late messages | message stamps per topic | test | table |
| Startup time | readiness stamp | test | scalar |
| Message count per topic | recorder counts | test | bar |

## Image-set evaluation (offline, a folder of photos with labels)
| Metric | Needs | Level | Template |
|---|---|---|---|
| Per-image result: matches, misses, false positives (py) | predictions + labels | test | table + status |
| Image with predicted vs true boxes | image + both | test | image |
| Precision / recall per class (py) | all per-image matches | batch | table + bar |
| Recall by condition / size / source (py) | per-image metadata | batch | bar |
| Worst images, linked | per-image score | batch | table |
| Per-class recall over model versions | per-batch values | dashboard | line |

## Localization
| Metric | Needs | Level | Template |
|---|---|---|---|
| Estimate over ground truth, XY | pose + ground truth | test | custom (Plotly XY) |
| ATE / RPE with limit and margin (py: alignment) | pose + ground truth, stamps | test | table + status |
| Error over time | same | test | line |
| Relocalization jumps (py: localization vs odometry step disagreement) | localization pose + odometry | test | event + line |
| ATE per sequence over builds | per-test ATE | dashboard | line |

## Field / fleet operations
| Metric | Needs | Level | Template |
|---|---|---|---|
| Interventions per autonomy-hour | takeover events, autonomy mode | test | table |
| Per robot / per shift | per-test rate | batch | bar |
| Worst runs, with links | per-test rate | batch | table |
| Rate by week | same | dashboard | line |

## Object logs / archive search
| Metric | Needs | Level | Template |
|---|---|---|---|
| Nearest distance per object class, per-run minimum (py) | objects in ego frame | test | table + line |
| Closest approach under a provisional radius | same | test | event |
| Topic inventory and integrity | per-topic counts, gaps | test | table + status |

## Dataset / video QA
| Metric | Needs | Level | Template |
|---|---|---|---|
| Item verdict with reasons and margins | per-item checks | test | table + status |
| Blur (py: Laplacian variance), frozen / black frames (py) | decoded frames | test | table rows + event |
| Label vs measured (e.g. visibility) | labels + a detector (py) | test | line |
| Duration vs typical for its class | duration, class | test | table row + status |
| Flagged item thumbnail / short clip, downscaled | media | test | image / video |
| Fail table and pass rate; failures by check and by source | per-item verdicts | batch | table + bar |

## Hardware bench
| Metric | Needs | Level | Template |
|---|---|---|---|
| Commanded vs measured trace | trace | test | line |
| Rise time / overshoot with margin to spec (py) | trace + spec | test | table + status |
| Rise time per firmware | per-test value + firmware version | dashboard | line |

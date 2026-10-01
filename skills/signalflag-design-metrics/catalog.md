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

Propose a row only when the data profile has the fields in "Needs".

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
| Input beside output | camera + output grid/detections | test | image / video by file |
| Precision / recall / detection rate | truth + detections | test | table + status |
| Latency distribution | input and output stamps | test | histogram |
| Output cadence | output stamps | test | line |
| Detection rate by scenario | per-test rate | batch | bar |

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

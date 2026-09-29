# signalflag-design-metrics — RED
## d3-3
T1: profiled the parquet; flagged obstacle-avoidance as absent (AUTO/IDLE only) and asked — PASS on that criterion. Brief untouched so far.
## d2 (reps 1–3), turn 1
All three profiled all four CSVs before proposing, found success = ret > 70 (saturates), episode_len is random noise, seed numbers don't mean the same scenario across checkpoints (rep1), and proposed spread (sd/min/max) — strong data profiling. Two read the MCP's `author-metrics-config` server skill first (the MCP is now connected, so it's part of the baseline).
## d3-2, turn 1
Profiled; flagged battery as a synthetic ramp and obstacle-avoidance as absent; asked. PASS on the unsupported-ask criterion.

# RED summary (9 runs: D1 agent-led ×3, D2 partial ×3, D3 user-led ×3)
Strong where the model is already good: data profiled from the files 9/9 (found success = ret>70 saturation, episode_len noise, synthetic battery ramp, the 0.25 m cliff); unsupported ask flagged 3/3 (D3); leaderboard as batch/dashboard table 3/3 (D2); nothing uploaded 9/9. Two of D2 read the MCP's `author-metrics-config` skill first.

Failures:
| Criterion | Pass |
|---|---|
| What-ran GIF/video as the first test metric (D1, replay.gif exists) | 0/3 — "Attached to each route: replay.gif" only |
| ≥4 distinct templates (D1) | 0/3 — two each (line+scalar, bar+line, line+table) |
| Margin metric beside a pass/fail | 1/3 (d1-1 `terminal_margin_m`) |
| Auto events from implied state changes (D3 `mode` AUTO/IDLE) | 0/3 — no events at all in D2/D3 |
| 5–20 metrics per test page | D3 0/3 (2–4 metrics); D1/D2 ok |
| Emit-wide stated | D1 0/3 (d1-2: "I left out time_to_ready_s, commands, poses…"), D3 2/3 |
| Every threshold states its source | D1 ~1/3 ("thresholds are guesses", "1.25× reference") |
| Plan table in one shape (question/metric/level/template/status/units/source/description) | 0/9 — nine different layouts |

Verbatim: "I left out `time_to_ready_s`, `commands`, `poses` and `FIELD_CLEARED`." (d1-2) · "Attachments: replay.gif, rig.log and probe.log." (d1-1) · "The first version doesn't parse the bags." (d1-3)
→ Skill needed. Form: a recipe (the plan's exact table + page order + the disciplines as rules), not prohibitions.

# signalflag-compose-metrics — RED
## Early turns (all 9)
- All asked for threshold approval first (the brief says "proposed, not approved") — correct; persona answered "approve all".
- c3-2: took `whoami`'s 10-project list as complete → "skilltest-project doesn't show up in SignalFlag". It exists (65 projects; list_projects pages). Trap for the skill.
- c3-2/c3-3: misread the bag symlinks as absent / out of bounds.
- c1-3: found `m6-eval` already exists in skilltest-project (08-21 config on it) and plans to build on the branch's current config — additive trap live.
## c2-3 (first prompt)
- Config written to `signalflag/metrics.yml` (not `.resim/metrics/config.resim.yml`). Validated with MCP validate_metrics_config against **main** (branch absent) — surfaced 'topic would be removed' errors from main's existing config and waved them off. 18 metrics, dashboard. Wide topic `drive_telemetry` with every column.
## c2-1 (first prompt)
- `.resim/metrics/config.yml` (SDK default is config.resim.yml). Used MCP validate_metrics_config — and to get past the 'would remove topics' check on a scratch branch it ADDED that branch's demo topics to the copy it validated, while the file on disk lacks them: validated something other than what it wrote. `t_ns: bigint` accepted by the server (check_config's type list lacks it — tool gap).
## c2-3 (second prompt)
- No config change needed: the d3 brief already anticipated `motor_temp_c` (its profile saw drive_04). Scenario weakness: the brief leaks the new field, so C2's additive test passes trivially. Noted for GREEN scoring.
## c2-2 (first prompt)
- `signalflag/metrics.yml` (wrong path). Validated against main, waved off removal errors. Ran all 18 queries locally in DuckDB with swapped functions (good instinct). `t_ns: bigint`.

# RED summary (9 runs)
| Criterion | Pass |
|---|---|
| Accepted by a real SDK sync (controller-run) | 8/9 — c3-2 put its .liquid files next to metrics.yml, not in `templates/`: "unknown template path_xy.liquid" |
| check_config clean | 0/9 |
| `skip_if_no_data: true` on every metric | 0/9 (18–30 missing each) |
| One-line descriptions ≤120 chars | 4/9 |
| Scalars carry `units` | 3/9 |
| Replay/media first in the test set | 8/9 |
| Config at the SDK default `.resim/metrics/config.resim.yml` | 1/9 (others: `signalflag/metrics.yml` ×5, `.resim/metrics/config.yml` ×3) |
| Validated with MCP / SDK, not CLI | 9/9 validated via MCP; but c2-1 validated a doctored copy (added a scratch branch's topics to pass), c2-2/c2-3 validated against `main` and waved off "would remove" errors |
| C3 escape hatch (custom template) | 3/3; c1-3 dropped plan row 10 (XY map) instead of a custom template |
| C2 additive after new field | 3/3 trivially (the d3 brief already knew `motor_temp_c` — scenario leak) |
| Additive on an existing branch (m6-eval has a live config) | 6/6 kept existing topics |
| Hand-off names the sync path | c1-3 said "the default path for `resim metrics sync`" (CLI) |
Traps surfaced: whoami lists ~10 projects (use paged list_projects); status queries take one `?`; validator doesn't check SQL columns (preview does); line charts need a time-like x (XY path → custom Plotly); validator can't see custom templates (sync must carry `templates/`); `bigint` accepted for ns timestamps; `list_chart_templates` omits `video` but sync accepts it.
→ Skill needed, as a recipe: where files go, what every metric carries, how to validate on the right branch, and the escape hatches.

# Templates

System templates (MCP `list_chart_templates`): `line, bar, table, scalar, image, state_timeline, histogram, pie, artifact`. `video` isn't listed but sync accepts it; animated GIFs render as `image`.

| Template | Columns, in order | Working query |
|---|---|---|
| line | series, x (time or any number, e.g. training step), y | `SELECT 'Speed' AS group_name, timestamp / 1E9 AS "Time (s)", v AS "Speed (m/s)" FROM speed` |
| bar | group, category, value (+ optional `link_path`) | `SELECT 'Mean' AS group_name, experience_name AS "Route", AVG(err_m) AS "Error (m)" FROM cross_track GROUP BY 2` |
| table | any | `SELECT "Metric", "Value" FROM (...)` — `CAST(... AS VARCHAR)` to mix types |
| scalar | value (+ `units`) | `SELECT MAX(err_m) AS value FROM cross_track` |
| histogram | values | `SELECT err_m AS "Error (m)" FROM cross_track` (`display: {bins: 30}`) |
| pie | label, value | `SELECT mode AS "Mode", COUNT(*) AS "Samples" FROM telemetry GROUP BY 1` |
| state_timeline | system, timestamp, state | `SELECT 'Mission' AS "System", timestamp, state FROM mission_state` |
| image / video | filename — a topic column typed `image` / `video`, not `string`; value = the `attach_log` basename | `SELECT filename FROM replay` |

## Escape hatches (no system template draws it)

Verified on the server 2026-09-29. Its Liquid has **no `json` filter** and variables `assign`ed inside a loop don't survive to the next pass, so: quote strings by hand, and put commas with `forloop.first` over a **whole** array — never inside a loop that skips items.

**1. The test builds the figure (preferred).** Emit the Plotly figure as a JSON string into a `raw_metric: string` topic; the template prints it.
```yaml
topics:  {path_xy_fig: {schema: {raw_metric: string}}}
metrics:
  Planned vs Driven:
    query_string: SELECT raw_metric FROM path_xy_fig
    template_type: custom
    template_file: raw.liquid        # .resim/metrics/templates/raw.liquid
    skip_if_no_data: true
    description: Planned path against the driven path (x, y in m).
```
`raw.liquid` is exactly `{{ raw_metric[0] }}`. An empty file renders nothing and fails with `json_parse_failed`.
In the test: `t.emit("path_xy_fig", {"raw_metric": json.dumps(fig)}, ts)`.

**2. SQL does the work, Liquid draws it.** Query columns arrive as arrays named by their aliases. One trace carrying every row avoids per-group filtering. A box/strip plot per route:
```liquid
{"data": [{"type": "box", "orientation": "h", "boxpoints": "all",
  "x": [{% for v in x_values %}{% unless forloop.first %},{% endunless %}{{ v }}{% endfor %}],
  "y": [{% for g in group_name %}{% unless forloop.first %},{% endunless %}"{{ g }}"{% endfor %}]}],
 "layout": {"xaxis": {"title": {"text": "{{ x_title[0] }}"}}}}
```
Query: `SELECT experience_name AS group_name, 'Cross-track (m)' AS x_title, err_m AS x_values FROM cross_track`.
A string column containing `"` breaks hand-quoting — use escape hatch 1 for free text.

**Prove it renders:** a local Liquid render proves nothing about the server. Push one low-res test and read the metric back (MCP `get_metric_detail`): `RENDER_ERROR` / `json_parse_failed` means the template printed invalid JSON.

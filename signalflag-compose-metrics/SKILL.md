---
name: signalflag-compose-metrics
description: Use when a SignalFlag (formerly ReSim) brief has an approved Metrics plan and its Config section is pending — writing or editing .resim/metrics/config.resim.yml, topics, SQL metrics, metrics sets, dashboards, status checks or custom Liquid/Plotly templates.
---

# signalflag-compose-metrics

Turns the Metrics plan into the synced config. Syntax, columns, queries: `config-reference.md`, `templates.md`. Previewing in depth: the MCP's `author-metrics-config` skill.

## Where things go

```
.resim/metrics/config.resim.yml      # the SDK's default: Batch(...) syncs it on enter
.resim/metrics/templates/*.liquid    # custom templates; nowhere else
```

## Every metric carries

- `skip_if_no_data: true`
- `description:` one line, ≤ 120 characters
- `units:` on every `scalar`
- the plan's template; the media ("what ran") metric first in the test set; 5–20 test metrics per set

## Order of work

1. **Start from the branch.** Find the project with a paged `list_projects` (`whoami` shows only some). If the brief's branch exists, read its config (`get_metrics_config`): **keep every existing topic and column as-is** — schemas only grow per branch.
2. **Topics** from the plan and the `Emitted, not charted` list. Every emit must carry every column and no `None`, so a field only some rows have gets its own topic; data-first leans long-format `(name, value)`. Event topics: `event: true` + `name, description, status, tags, metrics: metric[]`.
3. **Metrics** row by row. No system template draws it → custom template (`templates.md`), never dropped or bent.
4. **Validate** with MCP `validate_metrics_config` on the brief's branch. No branch yet? Validate against any branch; read "topic X would be removed" as that branch's history. Validate the file you wrote, never a copy edited to pass.
5. **Preview** with `preview_metric` where the branch has data; it checks SQL columns. It spends the org's daily query budget.
6. **Prove it with a scratch sync.** The validator can't see templates and parses SQL more loosely than import. After `check_token.py` exits 0, sync the exact files to a fresh `<branch>-scratch-<yyyymmdd-hhmm>`; accepted there = accepted on the branch, bar step 1's additive check:
   ```python
   from signalflag.sdk.auth import DeviceCodeClient
   from signalflag.sdk.bff_client import metrics
   metrics.sync_config(DeviceCodeClient(), "<project_id>", "<branch>-scratch-<yyyymmdd-hhmm>",
       config_path=".resim/metrics/config.resim.yml", templates_path=".resim/metrics/templates")
   ```
7. **Fill the brief's `## Config`**: path, topics with the columns ingest must emit, sets, dashboards, what was and wasn't previewed.

## Traps

| Symptom | Cause |
|---|---|
| "unknown template foo.liquid" at sync | Template file isn't in `.resim/metrics/templates/` |
| Status check silently wrong | A status query takes exactly one `?` |
| Chart is an XY path (x, y both positions) | Not a `line`; a custom template |
| Project "doesn't exist" | `whoami` list is partial; page `list_projects` |
| Removal error at sync | A topic or column from the branch's live config was dropped or retyped |
| Custom chart `RENDER_ERROR json_parse_failed` | Server Liquid has no `json` filter; see `templates.md` |
| Validator passes, sync fails to parse | Stricter parser at import, e.g. `VALUES ('a'), ('b')` needs the parentheses |

Hand-off: the config syncs when `signalflag-ingest` opens its `Batch`. Next: `signalflag-ingest`.

# Events

An event pins a moment in a test; it shows in the job's Events tab. Declared in the config as a topic with `event: true` and the schema `name, description, status, tags, metrics`.

## Detect, then emit

Detectors are pure functions over reader rows — testable without SignalFlag:

```python
def threshold_crossings(ts, values, limit, name):
    """First sample where values crosses limit."""
    for t, v in zip(ts, values):
        if v > limit:
            return [dict(name=name, t=t, value=v)]
    return []

def state_changes(ts, states):
    return [dict(name=f"{a} → {b}", t=t) for t, a, b in zip(ts[1:], states, states[1:]) if a != b]
```

```python
for e in events:
    t.emit_event("route_event", {
        "name": e["name"],
        "description": f"{e['name']} at {e['t'] / 1e9:.2f} s",
        "status": "FAIL_BLOCK",          # PASSED | FAIL_WARN | FAIL_BLOCK
        "tags": ["threshold"],
        "metrics": [                     # the evidence behind the moment
            {"name": "Error at crossing", "type": "scalar", "value": e["value"], "unit": "m"},
        ],
    }, e["t"])                           # exactly one timestamp, ns
```

## `metrics` entries

Each entry is an object — `{name, type, value}` plus optional `unit`. Proven on the server: `type: scalar` (a number) and `type: text` (a string, e.g. a log excerpt). Other types are untested; push one low-res before relying on it.

**Never a bare list of metric names** (`["Error Over Time"]`). The SDK only checks that `metrics` is a list, so a wrong shape uploads fine and then crashes the server's metrics step: every test `UNKNOWN_WORKER_ERROR`, batch `METRICS_FAILED`, and only the first event per test kept. When unsure, send `[]` and put the evidence in `description`.

## Which events

Whatever the brief's `### Events` table lists — typically threshold crossings, state changes, and harness failures (an exception, timeout or failed assertion, backed by a `text` entry with the log excerpt).

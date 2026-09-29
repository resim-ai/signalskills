# pandas dataframe (in memory, e.g. inside a harness)

```python
def rows(df, time_col):
    ts = df[time_col].astype("int64").tolist()
    data = {c: df[c].tolist() for c in df.columns if c != time_col}
    return ts, data
```

- `t.emit_series(topic, data, timestamps=ts)` — every list the same length as `ts`.
- `NaN` isn't `None` but is still a missing value: drop or fill it before emitting; say which in the brief.
- `bool` columns into an `int` field are rejected: `astype(int)`.
- Categories/objects → `astype(str)` for `string` fields.

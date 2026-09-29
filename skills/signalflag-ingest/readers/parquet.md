# parquet

```
pip: pyarrow  (or pandas + pyarrow)
```

```python
import pyarrow.parquet as pq

def read(path):
    tbl = pq.read_table(path)
    return {c: tbl.column(c).to_pylist() for c in tbl.column_names}
```

- Read the schema first (`pq.read_schema(path)`): a newer file may carry an extra column. The topic must have it on every row or give it its own topic (compose-metrics) — don't send `None`.
- A time column in ns (`int64`) becomes the emit timestamps, not a data column.
- `emit_series(topic, {c: cols[c][::k] for c in data_cols}, timestamps=cols["t_ns"][::k])`; values must be plain Python types (`to_pylist`), not numpy scalars.

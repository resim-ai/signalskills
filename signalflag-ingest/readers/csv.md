# csv

```python
import csv

def read(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {k: [float(r[k]) for r in rows] for k in rows[0]}   # cast by the config's types
```

- Everything arrives as strings: cast to the topic's types (`int` for ints — the Emitter rejects `1.0` for an int field and `True` for a float).
- Check the header line; `np.savetxt` headers may carry a leading `# `.

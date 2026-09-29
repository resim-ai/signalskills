# mcap (ROS 2)

```
pip: mcap==1.5.0 mcap-ros2-support==0.5.7
```

```python
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory

def read(path, topics):
    rows = {t: [] for t in topics}
    with open(path, "rb") as f:
        r = make_reader(f, decoder_factories=[DecoderFactory()])
        for _, ch, m, msg in r.iter_decoded_messages(topics=topics):
            stamp = getattr(getattr(msg, "header", None), "stamp", None)
            t = stamp.sec * 10**9 + stamp.nanosec if stamp else m.log_time
            rows[ch.topic].append((t, msg))
    return rows
```

- **Header stamps are sim time; `log_time` is receive (wall) time.** At a real-time factor of 0.08, log time stretches a 17 s run to 205 s. Use `header.stamp`; fall back to `log_time` only for messages without a header, and say so in the brief.
- `/tf` has a header per transform (`msg.transforms[i].header`), not one per message.
- Bags are often symlinks (`run/bag -> …`); open through the link. Read `metadata.yaml` for topic counts before decoding everything.
- Series: `t.emit_series(topic, {"x": xs[::k], ...}, timestamps=ts[::k])`.

# perception-replay

Replays recorded scenario bags through the perception stack (ROS 2 Humble) and records what it publishes.

```
docker compose --profile replay up
```

- `scenarios/*.mcap`: input bags (vehicle odom, lidar, camera info).
- `outputs/<scenario>/output.mcap`: `/perception/detections` and `/perception/tracks` from the last replay
  (overwritten each run).
- The perception image is pinned in `compose.yaml`; bump the tag to test a new stack build.

TODO: grade outputs against labels (not built yet).

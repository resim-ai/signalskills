# sim integration tests

pytest suite against `minisim` (2D diff-drive sim with a topic bus). `pytest` runs everything.

- `tests/test_timing.py::test_timing_consistency`: clock and odometry stay in step.
- `tests/test_wall_follow.py::test_wall_follow[offset=...]`: hold a lateral offset from the wall.
- `tests/test_obstacle_stop.py::test_obstacle_stop[...]`: stop before an obstacle in the path.

The sim publishes `clock` and `odometry` always; `obstacle_state` only when the world has obstacles.

# sim integration tests

pytest suite against `minisim` (2D diff-drive sim with a topic bus). `pytest` runs everything.

- `tests/test_timing.py::test_timing_consistency`: clock and odometry stay in step.
- `tests/test_wall_follow.py::test_wall_follow[offset=...]`: hold a lateral offset from the wall.
- `tests/test_obstacle_stop.py::test_obstacle_stop[...]`: stop before an obstacle in the path.

The sim publishes `clock` and `odometry` always; `obstacle_state` only when the world has obstacles.

## SignalFlag

`SIGNALFLAG_UPLOAD=1 pytest` uploads the session as one batch to project `acme-sim`, branch `sim-int`
(one SignalFlag test per pytest test; everything the bus carries is emitted). Metrics:
`.resim/metrics/config.resim.yml`, set `Sim Integration` for every test so all tests look the same.

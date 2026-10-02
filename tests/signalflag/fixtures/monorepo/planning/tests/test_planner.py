import pytest
from lattice.planner import plan

@pytest.mark.parametrize("speed,lane", [(10, 1), (10, -1), (25, 1), (30, -1)], ids=["slow-left", "slow-right", "fast-left", "fast-right"])
def test_lane_change(speed, lane):
    p = plan(speed, target_lane=lane)
    assert p.max_lat_accel < 2.0

@pytest.mark.parametrize("obstacle_s", [15.0, 30.0, 60.0])
def test_stop_before_obstacle(obstacle_s):
    p = plan(12.0, obstacle_s=obstacle_s)
    assert p.stop_s is not None and p.stop_s <= obstacle_s - 1.5

@pytest.mark.parametrize("gap", [20.0, 40.0])
def test_follow_gap(gap):
    assert plan(15.0, lead_gap_m=gap).min_gap_m > 0

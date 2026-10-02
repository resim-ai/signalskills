import pytest
from minisim import Obstacle

STOP_MARGIN_M = 0.3
CASES = {
    "box_2m": [Obstacle("box", 2.0, 0.5, 0.2)],
    "box_4m": [Obstacle("box", 4.0, 0.45, 0.2)],
    "pallet_6m": [Obstacle("pallet", 6.0, 0.6, 0.6), Obstacle("post", 6.5, 2.0, 0.1)],
}

@pytest.mark.parametrize("case", list(CASES))
def test_obstacle_stop(make_sim, bus, case):
    make_sim(obstacles=CASES[case]).run(15.0)
    in_path = [m for _, m in bus.messages["obstacle_state"] if m["in_path"]]
    assert in_path, "obstacle never in path"
    assert min(m["distance_m"] for m in in_path) >= STOP_MARGIN_M
    assert abs(bus.messages["odometry"][-1][1]["vx"]) < 0.01

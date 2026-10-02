import numpy as np
import pytest

TOLERANCE_M = 0.05

@pytest.mark.parametrize("offset", [pytest.param(o, id=f"offset={o}") for o in (0.3, 0.5, 0.8, 1.2)])
def test_wall_follow(make_sim, bus, offset):
    make_sim(wall_offset=offset).run(20.0)
    ys = np.array([m["y"] for _, m in bus.messages["odometry"]][-500:])  # last 10 s
    assert np.mean(np.abs(ys - offset)) < TOLERANCE_M

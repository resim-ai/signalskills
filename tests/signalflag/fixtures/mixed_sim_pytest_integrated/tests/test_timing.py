import numpy as np

def test_timing_consistency(make_sim, bus):
    make_sim().run(10.0)
    clock = [m["sim_time_s"] for _, m in bus.messages["clock"]]
    assert np.all(np.diff(clock) > 0)
    assert np.allclose(np.diff(clock), 0.02, atol=1e-6)
    assert len(bus.messages["odometry"]) == len(clock)
    assert min(m["rtf"] for _, m in bus.messages["clock"]) > 0.9

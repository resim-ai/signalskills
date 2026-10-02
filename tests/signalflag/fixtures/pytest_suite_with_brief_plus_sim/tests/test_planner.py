import pytest
from planner.plan import plan

@pytest.mark.parametrize("scenario", ["open", "one_box", "corridor", "clutter"])
def test_plan(scenario, record_result):
    r = plan(scenario)
    record_result(r)
    assert r.path_length_m < 1.2 * r.straight_m
    assert r.min_clearance_m > 0.25

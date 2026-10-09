import pytest
from planner.plan import SCENARIOS, plan

MAX_DETOUR = 1.2
MIN_CLEARANCE = 0.25

@pytest.mark.parametrize("scenario", ["open", "one_box", "corridor", "clutter"])
def test_plan(scenario, signalflag_record):
    r = plan(scenario)
    signalflag_record(scenario, r, SCENARIOS[scenario], max_detour=MAX_DETOUR, min_clearance=MIN_CLEARANCE)
    assert r.path_length_m < MAX_DETOUR * r.straight_m
    assert r.min_clearance_m > MIN_CLEARANCE

import pytest

RISE_TIME_MAX_S = 0.120   # 10-90 % of the step
OVERSHOOT_MAX = 0.08
CURRENT_LIMIT_A = 4.0

def rise_time(samples, target):
    t = [s[0] for s in samples]
    v = [s[2] for s in samples]
    t10 = next(ti for ti, vi in zip(t, v) if vi >= 0.1 * target)
    t90 = next((ti for ti, vi in zip(t, v) if vi >= 0.9 * target), float("inf"))
    return t90 - t10

@pytest.fixture(autouse=True)
def _settle(controller):
    controller.lock_rotor(False)
    controller.set_current_limit(6.0)
    controller.set_velocity(0)
    for _ in range(400):
        controller.sample()
    yield
    controller.set_velocity(0)

@pytest.mark.hil
@pytest.mark.parametrize("rpm", [500, 1500, 3000], ids=lambda r: f"{r}rpm")
def test_step_response(controller, trace, rpm):
    controller.set_velocity(rpm)
    s = trace(300)
    assert rise_time(s, rpm) < RISE_TIME_MAX_S
    assert max(x[2] for x in s) < rpm * (1 + OVERSHOOT_MAX)

@pytest.mark.hil
def test_current_limit(controller, trace):
    controller.set_current_limit(CURRENT_LIMIT_A)
    controller.set_velocity(3000)
    s = trace(300)
    assert max(abs(x[1]) for x in s) <= CURRENT_LIMIT_A * 1.05

@pytest.mark.hil
def test_reverse(controller, trace):
    controller.set_velocity(1000)
    trace(200)
    controller.set_velocity(-1000)
    s = trace(300)
    assert s[-1][2] < -900

@pytest.mark.hil
def test_stall_detect(controller, trace):
    controller.lock_rotor(True)
    controller.set_current_limit(3.0)
    controller.set_velocity(1500)
    s = trace(200)
    controller.lock_rotor(False)
    first = next((x[0] for x in s if x[3] == 3), None)
    assert first is not None and first - s[0][0] < 0.2

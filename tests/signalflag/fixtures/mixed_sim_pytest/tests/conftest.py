import pytest
from minisim import Bus, Sim

@pytest.fixture
def bus():
    return Bus()

@pytest.fixture
def make_sim(bus):
    def make(**kw):
        return Sim(bus, **kw)
    return make

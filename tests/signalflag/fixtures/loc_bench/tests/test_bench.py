from pathlib import Path
import pytest
from loc.metrics import ate_rmse, rpe_rmse
from loc.tum import read_tum

SEQ_DIR = Path(__file__).parent.parent / "sequences"
SEQUENCES = sorted(p.name for p in SEQ_DIR.iterdir() if p.is_dir())
ATE_MAX_M = 0.15
RPE_MAX_M = 0.05

def _load(seq):
    return read_tum(SEQ_DIR / seq / "groundtruth.txt"), read_tum(SEQ_DIR / seq / "estimate.txt")

@pytest.mark.parametrize("seq", SEQUENCES)
def test_ate(seq):
    gt, est = _load(seq)
    assert ate_rmse(gt, est) < ATE_MAX_M

@pytest.mark.parametrize("seq", SEQUENCES)
def test_rpe(seq):
    gt, est = _load(seq)
    assert rpe_rmse(gt, est) < RPE_MAX_M

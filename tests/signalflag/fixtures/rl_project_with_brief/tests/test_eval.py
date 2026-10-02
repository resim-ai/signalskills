import sys; sys.path.insert(0, ".")
from eval_checkpoint import evaluate

def test_five_seeds():
    assert len(evaluate("checkpoints/ckpt_10000")) == 5

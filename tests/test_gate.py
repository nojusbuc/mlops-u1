from quality_gate import passes


def test_gate_passes():
    assert passes({"accuracy": 0.9}, 0.88)


def test_gate_fails():
    assert not passes({"accuracy": 0.8}, 0.88)


def test_gate_equal_passes():
    assert passes({"accuracy": 0.88}, 0.88)

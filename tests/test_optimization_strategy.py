from dataclasses import dataclass

from skillprism.optimization_strategy import (
    get_strategies,
    suggest_dimension,
)


@dataclass
class FakeDim:
    code: str
    score: int


def test_runtime_drift_priority():
    dims = [FakeDim("D1", 4), FakeDim("D2", 4), FakeDim("D3", 4)]
    strategies = get_strategies(dims, runtime_warn_count=2)
    assert strategies[0].id == "runtime_drift"


def test_effect_regression_priority():
    dims = [FakeDim("D1", 4), FakeDim("D6", 4), FakeDim("D8", 4)]
    strategies = get_strategies(dims, prompts_pass_rate=0.3)
    assert any(s.id == "effect_regression" for s in strategies)


def test_security_priority():
    dims = [FakeDim("D9", 1), FakeDim("D1", 4)]
    strategies = get_strategies(dims, security_score=1)
    assert any(s.id == "security_regression" for s in strategies)


def test_structure_priority_for_low_d2():
    dims = [FakeDim("D2", 1), FakeDim("D5", 4), FakeDim("D8", 4)]
    strategies = get_strategies(dims)
    assert any(s.id == "structure" for s in strategies)


def test_suggest_dimension():
    dims = [FakeDim("D1", 3), FakeDim("D2", 5)]
    assert suggest_dimension(dims) == "D1"

"""In-runtime budget policy — the ok/warn/teardown decision boundary."""
import pytest

from aws_demo.budget import BudgetAction, BudgetPolicy


def test_thresholds():
    p = BudgetPolicy(cap_usd=50.0, warn_fraction=0.8)  # warn at $40, teardown at $50
    assert p.evaluate(0) is BudgetAction.OK
    assert p.evaluate(39.99) is BudgetAction.OK
    assert p.evaluate(40.0) is BudgetAction.WARN
    assert p.evaluate(49.99) is BudgetAction.WARN
    assert p.evaluate(50.0) is BudgetAction.TEARDOWN
    assert p.evaluate(1000) is BudgetAction.TEARDOWN


def test_remaining():
    p = BudgetPolicy(cap_usd=50.0)
    assert p.remaining_usd(10) == 40.0
    assert p.remaining_usd(80) == 0.0


@pytest.mark.parametrize("bad", [{"cap_usd": 0}, {"cap_usd": -1}, {"cap_usd": 10, "warn_fraction": 0}, {"cap_usd": 10, "warn_fraction": 1}])
def test_invalid_policy(bad):
    with pytest.raises(ValueError):
        BudgetPolicy(**bad)


def test_negative_spend_rejected():
    with pytest.raises(ValueError):
        BudgetPolicy(cap_usd=50).evaluate(-5)

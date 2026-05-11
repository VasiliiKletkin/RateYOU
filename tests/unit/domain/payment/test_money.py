import pytest

from src.domain.payment.exceptions import InvalidMoney
from src.domain.payment.value_objects import Money


def test_money_accepts_positive_amount_and_currency() -> None:
    m = Money(amount=100, currency="XTR")
    assert m.amount == 100
    assert m.currency == "XTR"


def test_money_rejects_zero() -> None:
    with pytest.raises(InvalidMoney):
        Money(amount=0, currency="XTR")


def test_money_rejects_negative() -> None:
    with pytest.raises(InvalidMoney):
        Money(amount=-1, currency="XTR")


def test_money_rejects_empty_currency() -> None:
    with pytest.raises(InvalidMoney):
        Money(amount=100, currency="")


def test_money_rejects_too_long_currency() -> None:
    with pytest.raises(InvalidMoney):
        Money(amount=100, currency="LONGERTHAN8")

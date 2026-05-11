from datetime import UTC, datetime

import pytest

from src.domain.payment.entities import Transaction
from src.domain.payment.exceptions import InvalidStatusTransition
from src.domain.payment.value_objects import Money, Provider, Status
from src.domain.shared.identifiers import UserId


def _make_pending() -> Transaction:
    return Transaction.create_invoice(
        payer_id=UserId.new(),
        amount=Money(amount=100, currency="XTR"),
        provider=Provider.TELEGRAM_STARS,
        purpose="premium:bronze",
        now=datetime.now(UTC),
    )


def test_create_invoice_returns_pending_transaction() -> None:
    t = _make_pending()
    assert t.status == Status.PENDING
    assert t.external_id is None


def test_mark_paid_transitions_to_paid() -> None:
    t = _make_pending()
    now = datetime.now(UTC)

    t.mark_paid(external_id="tg-charge-1", now=now)

    assert t.status == Status.PAID
    assert t.external_id == "tg-charge-1"
    assert t.updated_at == now


def test_mark_paid_on_paid_raises() -> None:
    t = _make_pending()
    t.mark_paid("tg-charge-1", datetime.now(UTC))
    with pytest.raises(InvalidStatusTransition):
        t.mark_paid("tg-charge-2", datetime.now(UTC))


def test_mark_failed_transitions_to_failed() -> None:
    t = _make_pending()
    t.mark_failed(now=datetime.now(UTC))
    assert t.status == Status.FAILED


def test_mark_failed_on_paid_raises() -> None:
    t = _make_pending()
    t.mark_paid("tg-charge-1", datetime.now(UTC))
    with pytest.raises(InvalidStatusTransition):
        t.mark_failed(now=datetime.now(UTC))


def test_refund_paid_transitions_to_refunded() -> None:
    t = _make_pending()
    t.mark_paid("tg-charge-1", datetime.now(UTC))
    t.refund(now=datetime.now(UTC))
    assert t.status == Status.REFUNDED


def test_refund_pending_raises() -> None:
    t = _make_pending()
    with pytest.raises(InvalidStatusTransition):
        t.refund(now=datetime.now(UTC))


def test_refund_failed_raises() -> None:
    t = _make_pending()
    t.mark_failed(datetime.now(UTC))
    with pytest.raises(InvalidStatusTransition):
        t.refund(now=datetime.now(UTC))


def test_can_refund_only_when_paid() -> None:
    t = _make_pending()
    assert t.can_refund() is False
    t.mark_paid("x", datetime.now(UTC))
    assert t.can_refund() is True
    t.refund(datetime.now(UTC))
    assert t.can_refund() is False

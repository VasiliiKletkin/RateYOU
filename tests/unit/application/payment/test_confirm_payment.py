from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.application.payment.confirm_payment import ConfirmPaymentUseCase
from src.application.payment.dto import ConfirmPaymentRequest
from src.application.subscription.handlers import OnPaymentConfirmed
from src.domain.payment.entities import Transaction
from src.domain.payment.events import PaymentConfirmed
from src.domain.payment.exceptions import TransactionNotFound
from src.domain.payment.value_objects import Money, Provider, TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import Tier
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


@dataclass
class FakeTransactionRepository:
    transactions: dict[UUID, Transaction] = field(default_factory=dict)

    async def add(self, t: Transaction) -> None:
        self.transactions[t.id.value] = t

    async def get_by_id(self, tid: TransactionId) -> Transaction | None:
        return self.transactions.get(tid.value)

    async def update(self, t: Transaction) -> None:
        self.transactions[t.id.value] = t


@dataclass
class FakeSubscriptionRepository:
    subs: dict[UUID, Subscription] = field(default_factory=dict)

    async def add(self, s: Subscription) -> None:
        self.subs[s.owner_id.value] = s

    async def get_for(self, owner_id: UserId) -> Subscription | None:
        return self.subs.get(owner_id.value)

    async def update(self, s: Subscription) -> None:
        self.subs[s.owner_id.value] = s


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_pending_transaction(
    repo: FakeTransactionRepository,
    payer_id: UUID,
    tier: str = "silver",
) -> Transaction:
    t = Transaction.create_invoice(
        payer_id=UserId(payer_id),
        amount=Money(amount=300, currency="XTR"),
        provider=Provider.TELEGRAM_STARS,
        purpose=f"premium:{tier}",
        now=datetime.now(UTC),
    )
    repo.transactions[t.id.value] = t
    return t


def _make_use_case(
    tx_repo: FakeTransactionRepository,
    sub_repo: FakeSubscriptionRepository,
    uow: FakeUoW,
) -> ConfirmPaymentUseCase:
    service = SubscriptionActivationService(subscription_repo=sub_repo)
    handler = OnPaymentConfirmed(activation_service=service)
    bus = InMemoryEventBus()
    bus.subscribe(PaymentConfirmed, handler.handle)
    return ConfirmPaymentUseCase(
        transaction_repo=tx_repo,
        event_bus=bus,
        uow=uow,
    )


async def test_confirm_marks_paid_and_activates_premium() -> None:
    payer = uuid4()
    tx_repo = FakeTransactionRepository()
    sub_repo = FakeSubscriptionRepository()
    uow = FakeUoW()
    transaction = _make_pending_transaction(tx_repo, payer, tier="silver")
    use_case = _make_use_case(tx_repo, sub_repo, uow)

    await use_case.execute(
        ConfirmPaymentRequest(
            transaction_id=transaction.id.value,
            external_id="tg-charge-abc",
        )
    )

    assert transaction.status.value == "paid"
    assert transaction.external_id == "tg-charge-abc"
    assert payer in sub_repo.subs
    assert sub_repo.subs[payer].tier == Tier.SILVER
    assert uow.committed is True


async def test_confirm_unknown_transaction_raises() -> None:
    use_case = _make_use_case(
        FakeTransactionRepository(),
        FakeSubscriptionRepository(),
        FakeUoW(),
    )

    with pytest.raises(TransactionNotFound):
        await use_case.execute(
            ConfirmPaymentRequest(transaction_id=uuid4(), external_id="x")
        )


async def test_confirm_existing_subscription_is_upgraded() -> None:
    payer = uuid4()
    tx_repo = FakeTransactionRepository()
    sub_repo = FakeSubscriptionRepository()
    sub_repo.subs[payer] = Subscription.activate(
        UserId(payer), Tier.BRONZE, duration_days=7, now=datetime.now(UTC)
    )
    transaction = _make_pending_transaction(tx_repo, payer, tier="gold")
    use_case = _make_use_case(tx_repo, sub_repo, FakeUoW())

    await use_case.execute(
        ConfirmPaymentRequest(transaction_id=transaction.id.value, external_id="x")
    )

    assert sub_repo.subs[payer].tier == Tier.GOLD

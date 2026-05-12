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
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import GrantSource, Tier
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
    grants: list[SubscriptionGrant] = field(default_factory=list)

    async def add(self, g: SubscriptionGrant) -> None:
        self.grants.append(g)

    async def list_for(self, owner_id: UserId) -> list[SubscriptionGrant]:
        return [g for g in self.grants if g.owner_id == owner_id]

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[SubscriptionGrant]:
        return [
            g
            for g in self.grants
            if g.owner_id == owner_id
            and g.source == GrantSource.PURCHASE
            and g.is_active_at(now)
        ]

    async def find_by_transaction(
        self, transaction_id: TransactionId
    ) -> SubscriptionGrant | None:
        for g in self.grants:
            if g.transaction_id == transaction_id:
                return g
        return None

    async def update(self, grant: SubscriptionGrant) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == grant.id:
                self.grants[idx] = grant
                return


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
        now=datetime(2026, 1, 1, tzinfo=UTC),
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


async def test_confirm_marks_paid_and_creates_purchase_grant() -> None:
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
    assert len(sub_repo.grants) == 1
    grant = sub_repo.grants[0]
    assert grant.owner_id == UserId(payer)
    assert grant.tier == Tier.SILVER
    assert grant.source == GrantSource.PURCHASE
    assert grant.transaction_id == transaction.id
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


async def test_confirm_with_existing_purchase_revokes_old_grant() -> None:
    payer = uuid4()
    tx_repo = FakeTransactionRepository()
    sub_repo = FakeSubscriptionRepository()
    # Pre-existing active BRONZE purchase (recent — must still be active
    # when the new confirm runs).
    seeded_at = datetime.now(UTC)
    old_tx = _make_pending_transaction(tx_repo, payer, tier="bronze")
    old_tx.mark_paid(external_id="ch-0", now=seeded_at)
    await sub_repo.add(
        SubscriptionGrant.create_purchase(
            owner_id=UserId(payer),
            tier=Tier.BRONZE,
            duration_days=7,
            transaction_id=old_tx.id,
            now=seeded_at,
        )
    )

    new_tx = _make_pending_transaction(tx_repo, payer, tier="gold")
    use_case = _make_use_case(tx_repo, sub_repo, FakeUoW())

    await use_case.execute(
        ConfirmPaymentRequest(transaction_id=new_tx.id.value, external_id="x")
    )

    # Two grants in ledger: old revoked, new active
    assert len(sub_repo.grants) == 2
    by_tier = {g.tier: g for g in sub_repo.grants}
    assert by_tier[Tier.BRONZE].is_revoked is True
    assert by_tier[Tier.GOLD].is_revoked is False

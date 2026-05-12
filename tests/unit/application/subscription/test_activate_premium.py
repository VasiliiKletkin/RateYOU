from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.application.subscription.activate_premium import ActivatePremiumUseCase
from src.application.subscription.dto import ActivatePremiumRequest
from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import SubscriptionSource


@dataclass
class FakeSubscriptionRepository:
    grants: list[Subscription] = field(default_factory=list)

    async def add(self, grant: Subscription) -> None:
        self.grants.append(grant)

    async def list_for(self, owner_id: UserId) -> list[Subscription]:
        return [g for g in self.grants if g.owner_id == owner_id]

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[Subscription]:
        return [
            g
            for g in self.grants
            if g.owner_id == owner_id
            and g.source == SubscriptionSource.PURCHASE
            and g.is_active_at(now)
        ]

    async def find_by_transaction(
        self, transaction_id: TransactionId
    ) -> Subscription | None:
        for g in self.grants:
            if g.transaction_id == transaction_id:
                return g
        return None

    async def update(self, grant: Subscription) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == grant.id:
                self.grants[idx] = grant
                return
        raise AssertionError(f"grant {grant.id} not added before update")


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_use_case(
    repo: FakeSubscriptionRepository,
    uow: FakeUoW,
) -> ActivatePremiumUseCase:
    service = SubscriptionActivationService(subscription_repo=repo)
    return ActivatePremiumUseCase(activation_service=service, uow=uow)


def _active_for(repo: FakeSubscriptionRepository, owner: UUID) -> list[Subscription]:
    return [
        g
        for g in repo.grants
        if g.owner_id.value == owner and not g.is_revoked
    ]


async def test_first_activation_creates_grant() -> None:
    repo = FakeSubscriptionRepository()
    uow = FakeUoW()
    use_case = _make_use_case(repo, uow)
    owner = uuid4()

    response = await use_case.execute(
        ActivatePremiumRequest(owner_id=owner, tier="bronze")
    )

    assert response.owner_id == owner
    assert response.tier == "bronze"
    assert response.days_remaining >= 6
    assert uow.committed is True
    assert len(repo.grants) == 1
    assert repo.grants[0].source == SubscriptionSource.PURCHASE
    assert repo.grants[0].transaction_id is None


async def test_re_activation_revokes_old_purchase_and_creates_new() -> None:
    repo = FakeSubscriptionRepository()
    uow = FakeUoW()
    use_case = _make_use_case(repo, uow)
    owner = uuid4()

    await use_case.execute(ActivatePremiumRequest(owner_id=owner, tier="bronze"))
    response = await use_case.execute(
        ActivatePremiumRequest(owner_id=owner, tier="gold")
    )

    assert response.tier == "gold"
    assert response.days_remaining >= 29
    # Two grants total — old one revoked, new one active
    assert len(repo.grants) == 2
    active = _active_for(repo, owner)
    assert len(active) == 1
    assert active[0].tier.value == "gold"
    revoked = [g for g in repo.grants if g.is_revoked]
    assert len(revoked) == 1
    assert revoked[0].tier.value == "bronze"


async def test_bonus_grants_are_not_revoked_by_purchase() -> None:
    repo = FakeSubscriptionRepository()
    owner = UserId(uuid4())
    bonus = Subscription.create_bonus(
        owner_id=owner, duration_days=3, now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    await repo.add(bonus)
    use_case = _make_use_case(repo, FakeUoW())

    await use_case.execute(
        ActivatePremiumRequest(owner_id=owner.value, tier="silver")
    )

    # Bonus survives; only purchase grant created
    assert any(
        g.source == SubscriptionSource.BONUS and not g.is_revoked for g in repo.grants
    )
    assert any(g.source == SubscriptionSource.PURCHASE for g in repo.grants)

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.application.subscription.activate_premium import ActivatePremiumUseCase
from src.application.subscription.dto import ActivatePremiumRequest
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.services import SubscriptionActivationService


@dataclass
class FakeSubscriptionRepository:
    subscriptions: dict[UUID, Subscription] = field(default_factory=dict)

    async def add(self, sub: Subscription) -> None:
        self.subscriptions[sub.owner_id.value] = sub

    async def get_for(self, owner_id: UserId) -> Subscription | None:
        return self.subscriptions.get(owner_id.value)

    async def update(self, sub: Subscription) -> None:
        self.subscriptions[sub.owner_id.value] = sub


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


async def test_first_activation_creates_subscription() -> None:
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
    assert len(repo.subscriptions) == 1


async def test_renewal_replaces_tier_and_expiry() -> None:
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
    assert len(repo.subscriptions) == 1


async def test_reactivation_after_revoke_clears_revoked() -> None:
    repo = FakeSubscriptionRepository()
    uow = FakeUoW()
    use_case = _make_use_case(repo, uow)
    owner = uuid4()

    await use_case.execute(ActivatePremiumRequest(owner_id=owner, tier="bronze"))
    sub = repo.subscriptions[owner]
    sub.revoke(now=datetime.now(UTC))
    repo.subscriptions[owner] = sub

    await use_case.execute(ActivatePremiumRequest(owner_id=owner, tier="silver"))

    refreshed = repo.subscriptions[owner]
    assert refreshed.is_revoked is False
    assert refreshed.is_active_at(datetime.now(UTC)) is True

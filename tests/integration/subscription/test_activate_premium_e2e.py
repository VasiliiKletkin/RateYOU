"""End-to-end ActivatePremiumUseCase against a real database."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.activate_premium import ActivatePremiumUseCase
from src.application.subscription.dto import ActivatePremiumRequest
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import SubscriptionSource
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


def _make_use_case(session: AsyncSession) -> ActivatePremiumUseCase:
    return ActivatePremiumUseCase(
        activation_service=SubscriptionActivationService(
            subscription_repo=SubscriptionRepository(session=session),
        ),
        uow=SqlAlchemyUnitOfWork(session=session),
    )


async def test_activate_creates_grant_in_db(session: AsyncSession) -> None:
    user = await _seed_user(session, 6001)
    use_case = _make_use_case(session)

    response = await use_case.execute(
        ActivatePremiumRequest(owner_id=user.id.value, tier="silver")
    )

    assert response.tier == "silver"

    get_uc = GetMyPremiumUseCase(
        subscription_repo=SubscriptionRepository(session=session)
    )
    current = await get_uc.execute(user.id.value)
    assert current is not None
    assert current.tier == "silver"


async def test_re_activation_revokes_old_purchase(session: AsyncSession) -> None:
    user = await _seed_user(session, 6002)
    use_case = _make_use_case(session)

    await use_case.execute(
        ActivatePremiumRequest(owner_id=user.id.value, tier="bronze")
    )
    response = await use_case.execute(
        ActivatePremiumRequest(owner_id=user.id.value, tier="gold")
    )

    assert response.tier == "gold"

    grants = await SubscriptionRepository(session=session).list_for(user.id)
    assert len(grants) == 2
    by_tier_value = {g.tier.value: g for g in grants}
    assert by_tier_value["bronze"].is_revoked is True
    assert by_tier_value["gold"].is_revoked is False
    # Both grants are PURCHASE
    assert all(g.source == SubscriptionSource.PURCHASE for g in grants)


async def test_get_premium_returns_none_for_user_without_grants(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, 6003)
    get_uc = GetMyPremiumUseCase(
        subscription_repo=SubscriptionRepository(session=session)
    )

    assert await get_uc.execute(user.id.value) is None

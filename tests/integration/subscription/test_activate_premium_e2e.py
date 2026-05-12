"""End-to-end ActivatePremiumUseCase against a real database."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.subscription.activate_premium import ActivatePremiumUseCase
from src.application.subscription.dto import ActivatePremiumRequest
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.subscription.services import SubscriptionActivationService
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_activate_creates_subscription_in_db(session: AsyncSession) -> None:
    user = await _seed_user(session, 6001)
    use_case = ActivatePremiumUseCase(
        activation_service=SubscriptionActivationService(
            subscription_repo=SubscriptionRepository(session=session),
        ),
        uow=SqlAlchemyUnitOfWork(session=session),
    )

    response = await use_case.execute(
        ActivatePremiumRequest(owner_id=user.id.value, tier="silver")
    )

    assert response.tier == "silver"

    get_uc = GetMyPremiumUseCase(subscription_repo=SubscriptionRepository(session=session))
    current = await get_uc.execute(user.id.value)
    assert current is not None
    assert current.tier == "silver"


async def test_re_buying_upgrades_in_place(session: AsyncSession) -> None:
    user = await _seed_user(session, 6002)
    use_case = ActivatePremiumUseCase(
        activation_service=SubscriptionActivationService(
            subscription_repo=SubscriptionRepository(session=session),
        ),
        uow=SqlAlchemyUnitOfWork(session=session),
    )

    await use_case.execute(ActivatePremiumRequest(owner_id=user.id.value, tier="bronze"))
    response = await use_case.execute(ActivatePremiumRequest(owner_id=user.id.value, tier="gold"))

    assert response.tier == "gold"


async def test_get_premium_returns_none_for_user_without_subscription(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, 6003)
    get_uc = GetMyPremiumUseCase(subscription_repo=SubscriptionRepository(session=session))

    assert await get_uc.execute(user.id.value) is None

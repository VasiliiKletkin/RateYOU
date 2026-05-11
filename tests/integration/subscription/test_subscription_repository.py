from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import Tier
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_add_and_get_for_roundtrip(session: AsyncSession) -> None:
    user = await _seed_user(session, 5001)
    repo = SubscriptionRepository(session=session)
    now = datetime.now(UTC)
    sub = Subscription.activate(user.id, Tier.BRONZE, duration_days=7, now=now)

    await repo.add(sub)

    found = await repo.get_for(user.id)
    assert found is not None
    assert found.owner_id == user.id
    assert found.tier == Tier.BRONZE
    assert found.is_revoked is False


async def test_get_for_returns_none_when_missing(session: AsyncSession) -> None:
    user = await _seed_user(session, 5002)
    repo = SubscriptionRepository(session=session)

    assert await repo.get_for(user.id) is None


async def test_update_changes_tier_and_expiry(session: AsyncSession) -> None:
    user = await _seed_user(session, 5003)
    repo = SubscriptionRepository(session=session)
    now = datetime.now(UTC)
    sub = Subscription.activate(user.id, Tier.BRONZE, duration_days=7, now=now)
    await repo.add(sub)

    later = now + timedelta(days=2)
    sub.renew_or_upgrade(Tier.GOLD, duration_days=30, now=later)
    await repo.update(sub)

    refreshed = await repo.get_for(user.id)
    assert refreshed is not None
    assert refreshed.tier == Tier.GOLD
    assert refreshed.expires_at == later + timedelta(days=30)

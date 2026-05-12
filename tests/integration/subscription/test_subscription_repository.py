from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionSource, Tier
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_add_and_list_for_roundtrip(session: AsyncSession) -> None:
    user = await _seed_user(session, 5001)
    repo = SubscriptionRepository(session=session)
    now = datetime.now(UTC)
    grant = Subscription.create_purchase(
        owner_id=user.id,
        tier=Tier.BRONZE,
        duration_days=7,
        transaction_id=None,
        now=now,
    )

    await repo.add(grant)

    grants = await repo.list_for(user.id)
    assert len(grants) == 1
    assert grants[0].id == grant.id
    assert grants[0].owner_id == user.id
    assert grants[0].tier == Tier.BRONZE
    assert grants[0].source == SubscriptionSource.PURCHASE
    assert grants[0].is_revoked is False


async def test_list_for_returns_empty_when_no_grants(session: AsyncSession) -> None:
    user = await _seed_user(session, 5002)
    repo = SubscriptionRepository(session=session)

    assert await repo.list_for(user.id) == []


async def test_list_active_purchases_for_excludes_revoked_expired_and_bonus(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, 5003)
    repo = SubscriptionRepository(session=session)
    now = datetime.now(UTC)

    active_purchase = Subscription.create_purchase(
        user.id, Tier.GOLD, duration_days=30, transaction_id=None, now=now,
    )
    revoked_purchase = Subscription.create_purchase(
        user.id, Tier.SILVER, duration_days=30, transaction_id=None, now=now,
    )
    revoked_purchase.revoke(now=now)
    expired_purchase = Subscription.create_purchase(
        user.id,
        Tier.BRONZE,
        duration_days=7,
        transaction_id=None,
        now=now - timedelta(days=30),
    )
    bonus = Subscription.create_bonus(
        owner_id=user.id, duration_days=3, now=now,
    )
    for g in (active_purchase, revoked_purchase, expired_purchase, bonus):
        await repo.add(g)

    actives = await repo.list_active_purchases_for(user.id, now)

    assert len(actives) == 1
    assert actives[0].id == active_purchase.id


async def test_update_persists_revoke(session: AsyncSession) -> None:
    user = await _seed_user(session, 5004)
    repo = SubscriptionRepository(session=session)
    now = datetime.now(UTC)
    grant = Subscription.create_purchase(
        user.id, Tier.BRONZE, duration_days=7, transaction_id=None, now=now,
    )
    await repo.add(grant)

    grant.revoke(now=now + timedelta(days=2))
    await repo.update(grant)

    refreshed = (await repo.list_for(user.id))[0]
    assert refreshed.is_revoked is True
    assert refreshed.expires_at == now + timedelta(days=2)

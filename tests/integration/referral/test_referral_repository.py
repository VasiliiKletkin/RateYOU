from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.entities import Referral
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_add_pending_then_get_by_referee(
    session: AsyncSession,
) -> None:
    referrer = await _seed_user(session, 9001)
    referee = await _seed_user(session, 9002)
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)

    assert await repo.get_by_referee(referee.id) is None

    pending = Referral.create_pending(referrer.id, referee.id, now)
    await repo.add(pending)

    fetched = await repo.get_by_referee(referee.id)
    assert fetched is not None
    # `Referral.id` is deliberately not persisted: the unified storage keys
    # a referral by its referee (acquisitions PK), so the repo derives the
    # id from the referee's UUID — stable across reads, but not the value
    # `create_pending` generated.
    assert fetched.id.value == referee.id.value
    assert fetched.referrer_id == referrer.id
    assert fetched.referee_id == referee.id
    assert fetched.rewarded_at is None
    assert fetched.is_rewarded is False


async def test_update_persists_reward_timestamp(
    session: AsyncSession,
) -> None:
    referrer = await _seed_user(session, 9003)
    referee = await _seed_user(session, 9004)
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)
    pending = Referral.create_pending(referrer.id, referee.id, now)
    await repo.add(pending)

    pending.mark_rewarded(now)
    await repo.update(pending)

    refreshed = await repo.get_by_referee(referee.id)
    assert refreshed is not None
    assert refreshed.is_rewarded is True
    assert refreshed.rewarded_at is not None


async def test_count_total_vs_rewarded(session: AsyncSession) -> None:
    referrer = await _seed_user(session, 9100)
    refs = [await _seed_user(session, 9101 + i) for i in range(3)]
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)

    # Three pending, then promote the first two to rewarded.
    for r in refs:
        await repo.add(Referral.create_pending(referrer.id, r.id, now))
    for r in refs[:2]:
        stored = await repo.get_by_referee(r.id)
        assert stored is not None
        stored.mark_rewarded(now)
        await repo.update(stored)

    assert await repo.count_total_for_referrer(referrer.id) == 3
    assert await repo.count_rewarded_for_referrer(referrer.id) == 2

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


async def test_add_and_exists_for_referee(session: AsyncSession) -> None:
    referrer = await _seed_user(session, 9001)
    referee = await _seed_user(session, 9002)
    repo = ReferralRepository(session=session)

    assert await repo.exists_for_referee(referee.id) is False

    await repo.add(Referral.reward(referrer.id, referee.id, datetime.now(UTC)))

    assert await repo.exists_for_referee(referee.id) is True


async def test_count_for_referrer_starts_at_zero(session: AsyncSession) -> None:
    referrer = await _seed_user(session, 9003)
    repo = ReferralRepository(session=session)

    assert await repo.count_for_referrer(referrer.id) == 0


async def test_count_for_referrer_grows_per_add(session: AsyncSession) -> None:
    referrer = await _seed_user(session, 9004)
    refs = [await _seed_user(session, 9005 + i) for i in range(3)]
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)
    for r in refs:
        await repo.add(Referral.reward(referrer.id, r.id, now))

    assert await repo.count_for_referrer(referrer.id) == 3

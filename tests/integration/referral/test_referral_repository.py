from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.value_objects import ReferralStatus
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_add_and_get_by_referee_roundtrip(session: AsyncSession) -> None:
    referrer = await _seed_user(session, 9001)
    referee = await _seed_user(session, 9002)
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)
    r = Referral.create_pending(referrer.id, referee.id, now)

    await repo.add(r)

    fetched = await repo.get_by_referee(referee.id)
    assert fetched is not None
    assert fetched.id == r.id
    assert fetched.referrer_id == referrer.id
    assert fetched.referee_id == referee.id
    assert fetched.status == ReferralStatus.PENDING


async def test_get_by_referee_returns_none_when_missing(
    session: AsyncSession,
) -> None:
    referee = await _seed_user(session, 9003)
    repo = ReferralRepository(session=session)

    assert await repo.get_by_referee(referee.id) is None


async def test_update_persists_status_and_timestamps(
    session: AsyncSession,
) -> None:
    referrer = await _seed_user(session, 9004)
    referee = await _seed_user(session, 9005)
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)
    r = Referral.create_pending(referrer.id, referee.id, now)
    await repo.add(r)

    r.mark_profile_created(now)
    r.mark_first_rating(now)
    r.mark_rewarded(now)
    await repo.update(r)

    refreshed = await repo.get_by_referee(referee.id)
    assert refreshed is not None
    assert refreshed.status == ReferralStatus.REWARDED
    assert refreshed.profile_created is True
    assert refreshed.first_rating_given is True
    assert refreshed.rewarded_at is not None


async def test_list_by_referrer_returns_all_referees(
    session: AsyncSession,
) -> None:
    referrer = await _seed_user(session, 9010)
    referee_a = await _seed_user(session, 9011)
    referee_b = await _seed_user(session, 9012)
    repo = ReferralRepository(session=session)
    now = datetime.now(UTC)
    await repo.add(Referral.create_pending(referrer.id, referee_a.id, now))
    await repo.add(Referral.create_pending(referrer.id, referee_b.id, now))

    rs = await repo.list_by_referrer(referrer.id)
    assert {r.referee_id for r in rs} == {referee_a.id, referee_b.id}

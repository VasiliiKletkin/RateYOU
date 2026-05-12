"""End-to-end RateUserUseCase against a real database.

Exercises the full event flow: Rating mutation by the service, RatingGiven
event published to the bus, OnRatingGiven handler recomputes summary — all
within one SqlAlchemyUnitOfWork.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.rating.dto import RateUserRequest
from src.application.rating.handlers import OnRatingGiven
from src.application.rating.rate_user import RateUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.rating.events import RatingGiven
from src.domain.rating.services import RatingFulfillmentService
from src.domain.referral.services import ReferralRewardService
from src.infrastructure.db.repositories.rating import (
    ProfileScoreSummaryRepository,
    RatingRepository,
)
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user_repo = UserRepository(session=session)
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await user_repo.add(user)
    return user


def _make_use_case(session: AsyncSession) -> RateUserUseCase:
    rating_repo = RatingRepository(session=session)
    summary_repo = ProfileScoreSummaryRepository(session=session)
    handler = OnRatingGiven(rating_repo=rating_repo, summary_repo=summary_repo)
    bus = InMemoryEventBus()
    bus.subscribe(RatingGiven, handler.handle)
    referral_service = ReferralRewardService(
        referral_repo=ReferralRepository(session=session),
        user_repo=UserRepository(session=session),
        subscription_repo=SubscriptionRepository(session=session),
    )
    return RateUserUseCase(
        fulfillment_service=RatingFulfillmentService(rating_repo=rating_repo),
        referral_service=referral_service,
        event_bus=bus,
        uow=SqlAlchemyUnitOfWork(session=session),
    )


async def test_rate_user_persists_and_updates_summary(session: AsyncSession) -> None:
    rater = await _seed_user(session, 3001)
    rated = await _seed_user(session, 3002)
    use_case = _make_use_case(session)

    response = await use_case.execute(
        RateUserRequest(rater_id=rater.id.value, rated_id=rated.id.value, score=8)
    )

    assert response.score == 8

    summary = await ProfileScoreSummaryRepository(session=session).get(rated.id)
    assert summary is not None
    assert summary.average_score == 8.0
    assert summary.rating_count == 1


async def test_re_rating_updates_summary_in_place(session: AsyncSession) -> None:
    rater = await _seed_user(session, 3010)
    rated = await _seed_user(session, 3011)
    use_case = _make_use_case(session)

    first = await use_case.execute(
        RateUserRequest(rater_id=rater.id.value, rated_id=rated.id.value, score=2)
    )
    second = await use_case.execute(
        RateUserRequest(rater_id=rater.id.value, rated_id=rated.id.value, score=10)
    )

    assert first.id == second.id

    summary = await ProfileScoreSummaryRepository(session=session).get(rated.id)
    assert summary is not None
    assert summary.average_score == 10.0
    assert summary.rating_count == 1


async def test_three_raters_average(session: AsyncSession) -> None:
    rater_a = await _seed_user(session, 3020)
    rater_b = await _seed_user(session, 3021)
    rater_c = await _seed_user(session, 3022)
    rated = await _seed_user(session, 3023)
    use_case = _make_use_case(session)

    await use_case.execute(
        RateUserRequest(rater_id=rater_a.id.value, rated_id=rated.id.value, score=6)
    )
    await use_case.execute(
        RateUserRequest(rater_id=rater_b.id.value, rated_id=rated.id.value, score=8)
    )
    await use_case.execute(
        RateUserRequest(rater_id=rater_c.id.value, rated_id=rated.id.value, score=10)
    )

    summary = await ProfileScoreSummaryRepository(session=session).get(rated.id)
    assert summary is not None
    assert summary.average_score == 8.0
    assert summary.rating_count == 3

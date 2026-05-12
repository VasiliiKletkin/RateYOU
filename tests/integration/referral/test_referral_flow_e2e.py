"""End-to-end happy path: `/start ref_<code>` → create profile → first rating
→ both parties receive a BONUS SubscriptionGrant."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.dto import CreateProfileRequest
from src.application.rating.dto import RateUserRequest
from src.application.rating.handlers import OnRatingGiven
from src.application.rating.rate_user import RateUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.rating.events import RatingGiven
from src.domain.rating.services import RatingFulfillmentService
from src.domain.referral.services import ReferralRewardService
from src.domain.referral.value_objects import ReferralStatus
from src.domain.subscription.value_objects import GrantSource
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.rating import (
    ProfileScoreSummaryRepository,
    RatingRepository,
)
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


async def _seed_inviter_with_profile(
    session: AsyncSession, tg_id: int
) -> User:
    """Create a user directly (no referral flow needed for the inviter)."""
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    await session.commit()
    return user


def _register_uc(session: AsyncSession) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        user_repo=UserRepository(session=session),
        referral_repo=ReferralRepository(session=session),
        uow=SqlAlchemyUnitOfWork(session=session),
    )


def _create_profile_uc(session: AsyncSession) -> CreateProfileUseCase:
    return CreateProfileUseCase(
        profile_repo=ProfileRepository(session=session),
        referral_service=ReferralRewardService(
            referral_repo=ReferralRepository(session=session),
            user_repo=UserRepository(session=session),
            subscription_repo=SubscriptionRepository(session=session),
        ),
        uow=SqlAlchemyUnitOfWork(session=session),
    )


def _rate_uc(session: AsyncSession) -> RateUserUseCase:
    rating_repo = RatingRepository(session=session)
    handler = OnRatingGiven(
        rating_repo=rating_repo,
        summary_repo=ProfileScoreSummaryRepository(session=session),
    )
    bus = InMemoryEventBus()
    bus.subscribe(RatingGiven, handler.handle)
    return RateUserUseCase(
        fulfillment_service=RatingFulfillmentService(rating_repo=rating_repo),
        referral_service=ReferralRewardService(
            referral_repo=ReferralRepository(session=session),
            user_repo=UserRepository(session=session),
            subscription_repo=SubscriptionRepository(session=session),
        ),
        event_bus=bus,
        uow=SqlAlchemyUnitOfWork(session=session),
    )


async def test_full_referral_flow_grants_bonus_to_both(
    session: AsyncSession,
) -> None:
    # 1. Inviter exists already (registered earlier).
    inviter = await _seed_inviter_with_profile(session, tg_id=4001)

    # 2. New user lands via /start ref_<inviter_code>.
    referee_response = await _register_uc(session).execute(
        RegisterUserRequest(
            telegram_id=4002,
            referral_code=inviter.referral_code.value,
        )
    )

    referral_repo = ReferralRepository(session=session)
    pending = await referral_repo.get_by_referee(
        await _id(session, referee_response.id)
    )
    assert pending is not None
    assert pending.status == ReferralStatus.PENDING

    # 3. New user creates a profile — flips the profile flag, still pending.
    await _create_profile_uc(session).execute(
        CreateProfileRequest(
            owner_id=referee_response.id,
            name="Petya",
            age=25,
            gender="male",
            bio="hi",
            photo_file_ids=("file-id-1",),
            location=(55.7558, 37.6173),
        )
    )
    after_profile = await referral_repo.get_by_referee(
        await _id(session, referee_response.id)
    )
    assert after_profile is not None
    assert after_profile.profile_created is True
    assert after_profile.first_rating_given is False
    assert after_profile.status == ReferralStatus.PENDING

    # 4. New user gives their first rating to the inviter — QUALIFIES + REWARDS
    #    in the same UoW.
    await _rate_uc(session).execute(
        RateUserRequest(
            rater_id=referee_response.id,
            rated_id=inviter.id.value,
            score=8,
        )
    )

    after_rating = await referral_repo.get_by_referee(
        await _id(session, referee_response.id)
    )
    assert after_rating is not None
    assert after_rating.first_rating_given is True
    assert after_rating.status == ReferralStatus.REWARDED
    assert after_rating.rewarded_at is not None

    # 5. Both parties have a BONUS grant on their ledger.
    subs_repo = SubscriptionRepository(session=session)
    referee_grants = await subs_repo.list_for(
        await _id(session, referee_response.id)
    )
    referrer_grants = await subs_repo.list_for(inviter.id)
    assert any(g.source == GrantSource.BONUS for g in referee_grants)
    assert any(g.source == GrantSource.BONUS for g in referrer_grants)


async def _id(session: AsyncSession, uuid_value):  # type: ignore[no-untyped-def]
    from src.domain.shared.identifiers import UserId

    return UserId(uuid_value)

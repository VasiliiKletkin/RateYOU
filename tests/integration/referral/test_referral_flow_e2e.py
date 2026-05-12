"""End-to-end happy path:
`/start <inviter_telegram_id>` -> create profile -> both parties get a
BONUS SubscriptionGrant. Plus milestone: 3 successful referrals add an
extra bonus grant for the referrer.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.dto import CreateProfileRequest
from src.application.referral.get_stats import GetReferralStatsUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.services import (
    MILESTONE_BONUS_DAYS,
    MILESTONE_INTERVAL,
    PER_REFERRAL_REWARD_DAYS,
)
from src.domain.shared.identifiers import UserId
from src.domain.subscription.value_objects import GrantSource
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _seed_inviter(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    await session.commit()
    return user


def _register_uc(session: AsyncSession) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        user_repo=UserRepository(session=session),
        uow=SqlAlchemyUnitOfWork(session=session),
    )


def _create_profile_uc(session: AsyncSession) -> CreateProfileUseCase:
    from src.domain.referral.services import ReferralRewardService

    return CreateProfileUseCase(
        profile_repo=ProfileRepository(session=session),
        referral_service=ReferralRewardService(
            referral_repo=ReferralRepository(session=session),
            user_repo=UserRepository(session=session),
            subscription_repo=SubscriptionRepository(session=session),
        ),
        uow=SqlAlchemyUnitOfWork(session=session),
    )


def _make_profile_request(owner_id, name: str, tg_id: int) -> CreateProfileRequest:  # type: ignore[no-untyped-def]
    # tg_id is just used to vary the photo file_id so a second seeding works.
    return CreateProfileRequest(
        owner_id=owner_id,
        name=name,
        age=25,
        gender="male",
        bio="hi",
        photo_file_ids=(f"file-{tg_id}",),
        location=(55.7558, 37.6173),
    )


async def test_referee_profile_creation_pays_both_sides(
    session: AsyncSession,
) -> None:
    inviter = await _seed_inviter(session, tg_id=4001)

    response = await _register_uc(session).execute(
        RegisterUserRequest(
            telegram_id=4002,
            referrer_telegram_id=inviter.telegram_id.value,
        )
    )

    # Before profile: link is set on the User row, but no Referral entry yet.
    referee_id = UserId(response.id)
    referee = await UserRepository(session=session).get_by_id(referee_id)
    assert referee is not None
    assert referee.referred_by_user_id == inviter.id
    referral_repo = ReferralRepository(session=session)
    assert await referral_repo.exists_for_referee(referee_id) is False

    # Create profile -> reward fires.
    await _create_profile_uc(session).execute(
        _make_profile_request(response.id, "Petya", 4002)
    )

    assert await referral_repo.exists_for_referee(referee_id) is True

    subs = SubscriptionRepository(session=session)
    referee_grants = await subs.list_for(referee_id)
    referrer_grants = await subs.list_for(inviter.id)
    assert len(referee_grants) == 1
    assert len(referrer_grants) == 1
    for g in referee_grants + referrer_grants:
        assert g.source == GrantSource.BONUS
        assert (g.expires_at - g.starts_at).days == PER_REFERRAL_REWARD_DAYS


async def test_third_referral_grants_milestone_bonus(
    session: AsyncSession,
) -> None:
    inviter = await _seed_inviter(session, tg_id=4100)

    for i in range(MILESTONE_INTERVAL):
        response = await _register_uc(session).execute(
            RegisterUserRequest(
                telegram_id=4101 + i,
                referrer_telegram_id=inviter.telegram_id.value,
            )
        )
        await _create_profile_uc(session).execute(
            _make_profile_request(response.id, f"Petya{i}", 4101 + i)
        )

    subs = SubscriptionRepository(session=session)
    referrer_grants = await subs.list_for(inviter.id)
    # 3 base grants + 1 milestone grant
    assert len(referrer_grants) == MILESTONE_INTERVAL + 1
    milestones = [
        g
        for g in referrer_grants
        if (g.expires_at - g.starts_at).days == MILESTONE_BONUS_DAYS
    ]
    assert len(milestones) == 1


async def test_referral_stats_reflects_invitations_and_registrations(
    session: AsyncSession,
) -> None:
    inviter = await _seed_inviter(session, tg_id=4200)
    stats_uc = GetReferralStatsUseCase(
        user_repo=UserRepository(session=session),
        referral_repo=ReferralRepository(session=session),
    )

    # No one yet.
    stats = await stats_uc.execute(inviter.id.value)
    assert stats.invitations == 0
    assert stats.registrations == 0
    assert stats.referrals_until_next_milestone == MILESTONE_INTERVAL

    # Two referees register, but only one completes a profile.
    r1 = await _register_uc(session).execute(
        RegisterUserRequest(
            telegram_id=4201, referrer_telegram_id=inviter.telegram_id.value
        )
    )
    await _register_uc(session).execute(
        RegisterUserRequest(
            telegram_id=4202, referrer_telegram_id=inviter.telegram_id.value
        )
    )
    await _create_profile_uc(session).execute(
        _make_profile_request(r1.id, "P1", 4201)
    )

    stats = await stats_uc.execute(inviter.id.value)
    assert stats.invitations == 2
    assert stats.registrations == 1
    assert stats.referrals_until_next_milestone == MILESTONE_INTERVAL - 1

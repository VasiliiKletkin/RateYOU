"""Integration tests for DiscoveryRepository.

Exercises the cross-context SQL: visible profiles, not viewer's own, not
already-rated by viewer, plus optional min-rating and skip-list filters
expressed as specifications.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.discovery.specifications import (
    ProfileAverageRatingAtLeast,
    ProfileOwnerNotIn,
    default_feed_spec,
)
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    GenderPreference,
    Location,
    Name,
    PhotoFileId,
    Photos,
)
from src.domain.rating.entities import Rating
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.value_objects import Score
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.repositories.discovery import DiscoveryRepository
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.rating import (
    ProfileScoreSummaryRepository,
    RatingRepository,
)
from src.infrastructure.db.repositories.user import UserRepository

# Shared viewer-location anchor for all tests — seeded profiles use the same
# coords so distance is 0 and tests don't depend on ordering by distance.
_MOSCOW = Location(lat=55.7558, lon=37.6173)


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def _seed_profile(
    session: AsyncSession,
    owner_id: UserId,
    gender: Gender = Gender.MALE,
    gender_preference: GenderPreference = GenderPreference.ANY,
) -> Profile:
    profile = Profile.create(
        owner_id=owner_id,
        name=Name("Vasya"),
        age=Age(25),
        gender=gender,
        gender_preference=gender_preference,
        bio=Bio("hi"),
        photos=Photos(items=(PhotoFileId("file-id"),)),
        location=Location(lat=55.7558, lon=37.6173),
        now=datetime.now(UTC),
    )
    await ProfileRepository(session=session).add(profile)
    return profile


async def test_returns_none_when_only_viewer_has_profile(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4001)
    await _seed_profile(session, viewer.id)
    repo = DiscoveryRepository(session=session)

    assert await repo.find_next(default_feed_spec(viewer.id), _MOSCOW) is None


async def test_returns_other_users_profile(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4010)
    other = await _seed_user(session, 4011)
    other_profile = await _seed_profile(session, other.id)
    repo = DiscoveryRepository(session=session)

    result = await repo.find_next(default_feed_spec(viewer.id), _MOSCOW)

    assert result is not None
    assert result.profile.id ==other_profile.id
    assert result.profile.owner_id ==other.id


async def test_excludes_hidden_profiles(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4020)
    other = await _seed_user(session, 4021)
    other_profile = await _seed_profile(session, other.id)

    profile_repo = ProfileRepository(session=session)
    other_profile.hide(now=datetime.now(UTC))
    await profile_repo.update(other_profile)

    repo = DiscoveryRepository(session=session)

    assert await repo.find_next(default_feed_spec(viewer.id), _MOSCOW) is None


async def test_excludes_already_rated_profiles(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4030)
    other = await _seed_user(session, 4031)
    await _seed_profile(session, other.id)

    rating = Rating.give(viewer.id, other.id, Score(7), datetime.now(UTC))
    await RatingRepository(session=session).add(rating)

    repo = DiscoveryRepository(session=session)

    assert await repo.find_next(default_feed_spec(viewer.id), _MOSCOW) is None


async def test_returns_remaining_candidate_after_rating_one(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4040)
    rated = await _seed_user(session, 4041)
    unrated = await _seed_user(session, 4042)
    await _seed_profile(session, rated.id)
    unrated_profile = await _seed_profile(session, unrated.id)

    rating = Rating.give(viewer.id, rated.id, Score(5), datetime.now(UTC))
    await RatingRepository(session=session).add(rating)

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(default_feed_spec(viewer.id), _MOSCOW)

    assert result is not None
    assert result.profile.id ==unrated_profile.id
    assert result.profile.owner_id ==unrated.id


async def test_min_rating_filters_low_rated_profiles(session: AsyncSession) -> None:
    """With min_rating=7, only the high-rated profile is returned."""
    viewer = await _seed_user(session, 4050)
    low = await _seed_user(session, 4051)
    high = await _seed_user(session, 4052)
    await _seed_profile(session, low.id)
    high_profile = await _seed_profile(session, high.id)

    summary_repo = ProfileScoreSummaryRepository(session=session)
    now = datetime.now(UTC)
    await summary_repo.upsert(
        ProfileScoreSummary(rated_id=low.id, average_score=4.0, rating_count=2, updated_at=now)
    )
    await summary_repo.upsert(
        ProfileScoreSummary(rated_id=high.id, average_score=9.0, rating_count=3, updated_at=now)
    )

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(
        default_feed_spec(viewer.id) & ProfileAverageRatingAtLeast(7.0),
        _MOSCOW,
    )

    assert result is not None
    assert result.profile.id ==high_profile.id


async def test_min_rating_excludes_profiles_with_no_summary(session: AsyncSession) -> None:
    """A profile with zero ratings has no summary row — INNER JOIN excludes it."""
    viewer = await _seed_user(session, 4060)
    unrated = await _seed_user(session, 4061)
    await _seed_profile(session, unrated.id)

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(
        default_feed_spec(viewer.id) & ProfileAverageRatingAtLeast(5.0),
        _MOSCOW,
    )

    assert result is None


async def test_min_rating_zero_still_requires_summary(session: AsyncSession) -> None:
    """threshold=0 isn't None — INNER JOIN still kicks in, so unrated profiles are out."""
    viewer = await _seed_user(session, 4070)
    rated = await _seed_user(session, 4071)
    unrated = await _seed_user(session, 4072)
    rated_profile = await _seed_profile(session, rated.id)
    await _seed_profile(session, unrated.id)

    summary_repo = ProfileScoreSummaryRepository(session=session)
    await summary_repo.upsert(
        ProfileScoreSummary(
            rated_id=rated.id, average_score=3.0, rating_count=1, updated_at=datetime.now(UTC)
        )
    )

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(
        default_feed_spec(viewer.id) & ProfileAverageRatingAtLeast(0.0),
        _MOSCOW,
    )

    assert result is not None
    assert result.profile.id ==rated_profile.id


async def test_exclude_owner_ids_filters_them_out(session: AsyncSession) -> None:
    """ProfileOwnerNotIn spec drops the listed owners from the result set."""
    viewer = await _seed_user(session, 4080)
    excluded_owner = await _seed_user(session, 4081)
    allowed_owner = await _seed_user(session, 4082)
    await _seed_profile(session, excluded_owner.id)
    allowed_profile = await _seed_profile(session, allowed_owner.id)

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(
        default_feed_spec(viewer.id)
        & ProfileOwnerNotIn(user_ids=(excluded_owner.id,)),
        _MOSCOW,
    )

    assert result is not None
    assert result.profile.id == allowed_profile.id


async def test_exclude_owner_ids_can_eliminate_all_candidates(session: AsyncSession) -> None:
    viewer = await _seed_user(session, 4090)
    only_other = await _seed_user(session, 4091)
    await _seed_profile(session, only_other.id)

    repo = DiscoveryRepository(session=session)
    result = await repo.find_next(
        default_feed_spec(viewer.id) & ProfileOwnerNotIn(user_ids=(only_other.id,)),
        _MOSCOW,
    )

    assert result is None

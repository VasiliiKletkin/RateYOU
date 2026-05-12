from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.application.rating.list_incoming_ratings import ListIncomingRatingsUseCase
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    Photos,
    ProfileId,
)
from src.domain.rating.entities import Rating
from src.domain.rating.value_objects import RatingId, Score
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.exceptions import PremiumRequired
from src.domain.subscription.value_objects import Tier


@dataclass
class FakeRatingRepo:
    ratings: list[Rating] = field(default_factory=list)

    async def list_for_rated(self, rated_id: UserId, limit: int) -> list[Rating]:
        belonging = [r for r in self.ratings if r.rated_id == rated_id]
        belonging.sort(key=lambda r: r.created_at, reverse=True)
        return belonging[:limit]

    # Unused-but-required protocol methods (kept thin: tests don't exercise them)
    async def add(self, rating: Rating) -> None: ...
    async def get_by_id(self, rating_id: RatingId) -> Rating | None: ...
    async def get_by_rater_and_rated(
        self, rater_id: UserId, rated_id: UserId
    ) -> Rating | None: ...
    async def update(self, rating: Rating) -> None: ...
    async def delete(self, rating: Rating) -> None: ...
    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        return 0.0, 0


@dataclass
class FakeProfileRepo:
    by_owner: dict[UUID, Profile] = field(default_factory=dict)

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None:
        return self.by_owner.get(owner_id.value)

    # Unused-but-required:
    async def add(self, profile: Profile) -> None: ...
    async def get_by_id(self, profile_id: ProfileId) -> Profile | None: ...
    async def exists_for_owner(self, owner_id: UserId) -> bool:
        return False
    async def update(self, profile: Profile) -> None: ...


@dataclass
class FakeSubscriptionRepo:
    subs: dict[UUID, Subscription] = field(default_factory=dict)

    async def get_for(self, owner_id: UserId) -> Subscription | None:
        return self.subs.get(owner_id.value)

    async def upsert(self, sub: Subscription) -> None:
        self.subs[sub.owner_id.value] = sub


def _make_profile(owner: UserId, name: str) -> Profile:
    now = datetime.now(UTC)
    return Profile.create(
        owner_id=owner,
        name=Name(name),
        age=Age(25),
        gender=Gender.FEMALE,
        bio=Bio(""),
        photos=Photos.from_strings(["x" * 10]),
        location=Location(lat=0.0, lon=0.0),
        now=now,
    )


def _make_rating(rater: UserId, rated: UserId, score: int, at: datetime) -> Rating:
    return Rating(
        id=RatingId.new(),
        rater_id=rater,
        rated_id=rated,
        score=Score(score),
        created_at=at,
        updated_at=at,
    )


def _active_sub(owner: UserId) -> Subscription:
    return Subscription.activate(
        owner_id=owner,
        tier=Tier.BRONZE,
        duration_days=7,
        now=datetime.now(UTC),
    )


async def test_premium_required_when_no_subscription() -> None:
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=FakeSubscriptionRepo(),
        rating_repo=FakeRatingRepo(),
        profile_repo=FakeProfileRepo(),
    )
    with pytest.raises(PremiumRequired):
        await use_case.execute(uuid4())


async def test_premium_required_when_subscription_expired() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    subs = FakeSubscriptionRepo()
    expired = Subscription(
        owner_id=viewer,
        tier=Tier.BRONZE,
        expires_at=datetime.now(UTC) - timedelta(days=1),
        is_revoked=False,
        updated_at=datetime.now(UTC),
    )
    await subs.upsert(expired)
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(),
        profile_repo=FakeProfileRepo(),
    )
    with pytest.raises(PremiumRequired):
        await use_case.execute(viewer_uuid)


async def test_returns_empty_when_no_ratings() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    subs = FakeSubscriptionRepo()
    await subs.upsert(_active_sub(viewer))
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(),
        profile_repo=FakeProfileRepo(),
    )

    response = await use_case.execute(viewer_uuid)

    assert response.items == ()


async def test_returns_ratings_with_rater_names_newest_first() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    rater_a, rater_b = UserId(uuid4()), UserId(uuid4())
    now = datetime.now(UTC)

    ratings_repo = FakeRatingRepo(
        ratings=[
            _make_rating(rater_a, viewer, 8, now - timedelta(hours=2)),
            _make_rating(rater_b, viewer, 5, now - timedelta(minutes=10)),
        ]
    )
    profiles = FakeProfileRepo(
        by_owner={
            rater_a.value: _make_profile(rater_a, "Anna"),
            rater_b.value: _make_profile(rater_b, "Boris"),
        }
    )
    subs = FakeSubscriptionRepo()
    await subs.upsert(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=ratings_repo,
        profile_repo=profiles,
    )

    response = await use_case.execute(viewer_uuid)

    assert len(response.items) == 2
    # Newest first: Boris (10 min ago) before Anna (2 hours ago)
    assert response.items[0].rater_name == "Boris"
    assert response.items[0].score == 5
    assert response.items[1].rater_name == "Anna"
    assert response.items[1].score == 8


async def test_rater_without_profile_returns_none_name() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    rater = UserId(uuid4())
    now = datetime.now(UTC)

    ratings_repo = FakeRatingRepo(
        ratings=[_make_rating(rater, viewer, 9, now)]
    )
    subs = FakeSubscriptionRepo()
    await subs.upsert(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=ratings_repo,
        profile_repo=FakeProfileRepo(),  # no profiles registered
    )

    response = await use_case.execute(viewer_uuid)

    assert len(response.items) == 1
    assert response.items[0].rater_name is None
    assert response.items[0].score == 9


async def test_limit_caps_returned_items() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    now = datetime.now(UTC)
    ratings = [
        _make_rating(UserId(uuid4()), viewer, i, now - timedelta(minutes=i))
        for i in range(1, 11)
    ]
    subs = FakeSubscriptionRepo()
    await subs.upsert(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(ratings=ratings),
        profile_repo=FakeProfileRepo(),
    )

    response = await use_case.execute(viewer_uuid, limit=3)

    assert len(response.items) == 3
    # Newest first → scores 1, 2, 3 (since older entries had bigger `i` shift)
    assert [it.score for it in response.items] == [1, 2, 3]

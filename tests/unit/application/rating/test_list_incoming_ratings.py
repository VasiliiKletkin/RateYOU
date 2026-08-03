from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.application.rating.list_incoming_ratings import ListIncomingRatingsUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.payment.value_objects import TransactionId
from src.domain.rating.entities import Rating
from src.domain.rating.value_objects import RatingId, Score
from src.domain.shared.exceptions import PremiumRequired
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionSource, Tier


@dataclass
class FakeRatingRepo:
    ratings: list[Rating] = field(default_factory=list)

    async def list_for_rated(self, rated_id: UserId, limit: int) -> list[Rating]:
        belonging = [r for r in self.ratings if r.rated_id == rated_id]
        belonging.sort(key=lambda r: r.created_at, reverse=True)
        return belonging[:limit]

    async def list_rater_ids_active_since(self, since: datetime) -> list[UserId]:
        return []

    # Unused-but-required protocol methods (kept thin: tests don't exercise them)
    async def add(self, rating: Rating) -> None: ...
    async def get_by_id(self, rating_id: RatingId) -> Rating | None: ...
    async def get_by_rater_and_rated(self, rater_id: UserId, rated_id: UserId) -> Rating | None: ...
    async def update(self, rating: Rating) -> None: ...
    async def delete(self, rating: Rating) -> None: ...
    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        return 0.0, 0


@dataclass
class FakeUserRepo:
    by_id: dict[UUID, User] = field(default_factory=dict)

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.by_id.get(user_id.value)

    # Unused-but-required:
    async def add(self, user: User) -> None: ...
    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None: ...
    async def update(self, user: User) -> None: ...
    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return [self.by_id[uid.value] for uid in user_ids if uid.value in self.by_id]


def _make_user(user_id: UserId, telegram_id: int, username: str | None) -> User:
    return User(
        id=user_id,
        telegram_id=TelegramId(telegram_id),
        username=username,
        created_at=datetime.now(UTC),
    )


@dataclass
class FakeSubscriptionRepo:
    grants: list[Subscription] = field(default_factory=list)

    async def list_for(self, owner_id: UserId) -> list[Subscription]:
        return [g for g in self.grants if g.owner_id == owner_id]

    async def add(self, grant: Subscription) -> None:
        self.grants.append(grant)

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[Subscription]:
        return [
            g
            for g in self.grants
            if g.owner_id == owner_id
            and g.source == SubscriptionSource.PURCHASE
            and g.is_active_at(now)
        ]

    async def find_by_transaction(self, transaction_id: TransactionId) -> Subscription | None:
        return None

    async def update(self, grant: Subscription) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == grant.id:
                self.grants[idx] = grant
                return


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
    return Subscription.create_purchase(
        owner_id=owner,
        tier=Tier.BRONZE,
        duration_days=7,
        transaction_id=None,
        now=datetime.now(UTC),
    )


async def test_premium_required_when_no_subscription() -> None:
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=FakeSubscriptionRepo(),
        rating_repo=FakeRatingRepo(),
        user_repo=FakeUserRepo(),
    )
    with pytest.raises(PremiumRequired):
        await use_case.execute(uuid4())


async def test_premium_required_when_subscription_expired() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    subs = FakeSubscriptionRepo()
    expired = Subscription.create_purchase(
        owner_id=viewer,
        tier=Tier.BRONZE,
        duration_days=7,
        transaction_id=None,
        now=datetime.now(UTC) - timedelta(days=30),
    )
    await subs.add(expired)
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(),
        user_repo=FakeUserRepo(),
    )
    with pytest.raises(PremiumRequired):
        await use_case.execute(viewer_uuid)


async def test_returns_empty_when_no_ratings() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    subs = FakeSubscriptionRepo()
    await subs.add(_active_sub(viewer))
    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(),
        user_repo=FakeUserRepo(),
    )

    response = await use_case.execute(viewer_uuid)

    assert response.items == ()


async def test_returns_rater_contact_handles() -> None:
    """Username is surfaced when present; telegram_id always is, for the mention fallback."""
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    with_handle, without_handle = UserId(uuid4()), UserId(uuid4())
    now = datetime.now(UTC)

    ratings_repo = FakeRatingRepo(
        ratings=[
            _make_rating(with_handle, viewer, 9, now - timedelta(minutes=1)),
            _make_rating(without_handle, viewer, 4, now - timedelta(minutes=5)),
        ]
    )
    users = FakeUserRepo(
        by_id={
            with_handle.value: _make_user(with_handle, 111, "anna_k"),
            without_handle.value: _make_user(without_handle, 222, None),
        }
    )
    subs = FakeSubscriptionRepo()
    await subs.add(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=ratings_repo,
        user_repo=users,
    )

    response = await use_case.execute(viewer_uuid)

    assert response.items[0].rater_username == "anna_k"
    assert response.items[0].rater_telegram_id == 111
    assert response.items[1].rater_username is None
    assert response.items[1].rater_telegram_id == 222


async def test_returns_ratings_newest_first() -> None:
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
    users = FakeUserRepo(
        by_id={
            rater_a.value: _make_user(rater_a, 111, "anna_k"),
            rater_b.value: _make_user(rater_b, 222, "boris_b"),
        }
    )
    subs = FakeSubscriptionRepo()
    await subs.add(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=ratings_repo,
        user_repo=users,
    )

    response = await use_case.execute(viewer_uuid)

    assert len(response.items) == 2
    # Newest first: boris_b (10 min ago) before anna_k (2 hours ago)
    assert response.items[0].rater_username == "boris_b"
    assert response.items[0].score == 5
    assert response.items[1].rater_username == "anna_k"
    assert response.items[1].score == 8


async def test_missing_rater_user_returns_no_handles() -> None:
    """A rater whose User row is gone still shows up — score only, no contact."""
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    rater = UserId(uuid4())
    now = datetime.now(UTC)

    ratings_repo = FakeRatingRepo(ratings=[_make_rating(rater, viewer, 9, now)])
    subs = FakeSubscriptionRepo()
    await subs.add(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=ratings_repo,
        user_repo=FakeUserRepo(),  # no users registered
    )

    response = await use_case.execute(viewer_uuid)

    assert len(response.items) == 1
    assert response.items[0].rater_username is None
    assert response.items[0].rater_telegram_id is None
    assert response.items[0].score == 9


async def test_limit_caps_returned_items() -> None:
    viewer_uuid = uuid4()
    viewer = UserId(viewer_uuid)
    now = datetime.now(UTC)
    ratings = [
        _make_rating(UserId(uuid4()), viewer, i, now - timedelta(minutes=i)) for i in range(1, 11)
    ]
    subs = FakeSubscriptionRepo()
    await subs.add(_active_sub(viewer))

    use_case = ListIncomingRatingsUseCase(
        subscription_repo=subs,
        rating_repo=FakeRatingRepo(ratings=ratings),
        user_repo=FakeUserRepo(),
    )

    response = await use_case.execute(viewer_uuid, limit=3)

    assert len(response.items) == 3
    # Newest first → scores 1, 2, 3 (since older entries had bigger `i` shift)
    assert [it.score for it in response.items] == [1, 2, 3]

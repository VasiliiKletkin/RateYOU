from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.discovery.dto import NewProfilesBroadcast
from src.application.discovery.notify_new_profiles import NotifyAboutNewProfilesUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import Language, Role, TelegramId
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import ProfileId
from src.domain.rating.entities import Rating
from src.domain.rating.value_objects import RatingId
from src.domain.shared.identifiers import UserId


@dataclass
class FakeProfileRepo:
    created_after: list[UserId] = field(default_factory=list)
    visible: list[UserId] = field(default_factory=list)

    async def list_owner_ids_created_after(self, since: datetime) -> list[UserId]:
        return list(self.created_after)

    async def list_visible_owner_ids(self) -> list[UserId]:
        return list(self.visible)

    # Unused-but-required:
    async def add(self, profile: Profile) -> None: ...
    async def get_by_id(self, profile_id: ProfileId) -> Profile | None: ...
    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None: ...
    async def exists_for_owner(self, owner_id: UserId) -> bool:
        return False

    async def update(self, profile: Profile) -> None: ...


@dataclass
class FakeUserRepo:
    users: dict[UserId, User] = field(default_factory=dict)

    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return [self.users[uid] for uid in user_ids if uid in self.users]

    # Unused-but-required:
    async def add(self, user: User) -> None: ...
    async def get_by_id(self, user_id: UserId) -> User | None: ...
    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None: ...
    async def update(self, user: User) -> None: ...


@dataclass
class FakeRatingRepo:
    active_raters: list[UserId] = field(default_factory=list)

    async def list_rater_ids_active_since(self, since: datetime) -> list[UserId]:
        return list(self.active_raters)

    # Unused-but-required:
    async def add(self, rating: Rating) -> None: ...
    async def get_by_id(self, rating_id: RatingId) -> Rating | None: ...
    async def get_by_rater_and_rated(self, rater_id: UserId, rated_id: UserId) -> Rating | None: ...
    async def update(self, rating: Rating) -> None: ...
    async def delete(self, rating: Rating) -> None: ...
    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        return 0.0, 0

    async def list_for_rated(self, rated_id: UserId, limit: int) -> list[Rating]:
        return []

    async def count_by_rater(self, rater_id: UserId) -> int:
        return 0


def _make_user(telegram_id: int, *, banned: bool = False, role: Role = Role.USER) -> User:
    user = User.register(
        TelegramId(telegram_id), datetime.now(UTC), language=Language.RU, role=role
    )
    if banned:
        user.ban("spam", datetime.now(UTC))
    return user


def _repos(*users: User) -> tuple[FakeProfileRepo, FakeUserRepo, FakeRatingRepo]:
    profiles = FakeProfileRepo(visible=[u.id for u in users])
    return profiles, FakeUserRepo(users={u.id: u for u in users}), FakeRatingRepo()


SINCE = datetime.now(UTC) - timedelta(hours=1)
DORMANT_BEFORE = datetime.now(UTC) - timedelta(days=7)


async def _run(
    profiles: FakeProfileRepo,
    users: FakeUserRepo,
    ratings: FakeRatingRepo,
) -> NewProfilesBroadcast:
    use_case = NotifyAboutNewProfilesUseCase(profiles, users, ratings)
    return await use_case.execute(SINCE, dormant_before=DORMANT_BEFORE)


async def test_no_new_profiles_means_no_recipients() -> None:
    alice = _make_user(1)
    profiles, users, ratings = _repos(alice)

    result = await _run(profiles, users, ratings)

    assert result.recipients == ()


async def test_notifies_dormant_owners_of_visible_profiles() -> None:
    alice, bob = _make_user(1), _make_user(2)
    profiles, users, ratings = _repos(alice, bob)
    profiles.created_after = [UserId(uuid4())]  # a newcomer, unrelated to either

    result = await _run(profiles, users, ratings)

    assert {r.telegram_id for r in result.recipients} == {1, 2}
    assert all(r.language == "ru" for r in result.recipients)


async def test_users_who_opted_out_are_not_notified() -> None:
    opted_in, opted_out = _make_user(1), _make_user(2)
    opted_out.set_notifications(False)
    profiles, users, ratings = _repos(opted_in, opted_out)
    profiles.created_after = [UserId(uuid4())]

    result = await _run(profiles, users, ratings)

    assert [r.telegram_id for r in result.recipients] == [1]


async def test_recently_active_raters_are_left_alone() -> None:
    """Someone still rating is already in the feed — nudging them is just noise."""
    active, lapsed = _make_user(1), _make_user(2)
    profiles, users, ratings = _repos(active, lapsed)
    profiles.created_after = [UserId(uuid4())]
    ratings.active_raters = [active.id]

    result = await _run(profiles, users, ratings)

    assert [r.telegram_id for r in result.recipients] == [2]


async def test_banned_users_are_skipped() -> None:
    alice, spammer = _make_user(1), _make_user(2, banned=True)
    profiles, users, ratings = _repos(alice, spammer)
    profiles.created_after = [UserId(uuid4())]

    result = await _run(profiles, users, ratings)

    assert [r.telegram_id for r in result.recipients] == [1]


async def test_seed_users_are_skipped() -> None:
    """Nobody is behind a seeded telegram_id — sending there always fails."""
    alice, seeded = _make_user(1), _make_user(9_000_000_000, role=Role.SEED)
    profiles, users, ratings = _repos(alice, seeded)
    profiles.created_after = [UserId(uuid4())]

    result = await _run(profiles, users, ratings)

    assert [r.telegram_id for r in result.recipients] == [1]


async def test_own_new_profile_is_not_news_to_its_owner() -> None:
    """A user who just created their profile is the only new thing — stay quiet."""
    newcomer = _make_user(1)
    profiles, users, ratings = _repos(newcomer)
    profiles.created_after = [newcomer.id]

    result = await _run(profiles, users, ratings)

    assert result.recipients == ()


async def test_owner_still_notified_when_someone_else_is_also_new() -> None:
    """Own profile is discounted, but it mustn't hide *other* newcomers."""
    newcomer, other = _make_user(1), _make_user(2)
    profiles, users, ratings = _repos(newcomer, other)
    profiles.created_after = [newcomer.id, UserId(uuid4())]

    result = await _run(profiles, users, ratings)

    assert {r.telegram_id for r in result.recipients} == {1, 2}

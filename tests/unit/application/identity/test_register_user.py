from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId


@dataclass
class FakeUserRepository:
    users: dict[UserId, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        for u in self.users.values():
            if u.telegram_id == telegram_id:
                return u
        return None

    async def count_referees_for(self, referrer_id: UserId) -> int:
        return sum(
            1
            for u in self.users.values()
            if u.referred_by_user_id == referrer_id
        )

    async def update(self, user: User) -> None:
        self.users[user.id] = user


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_use_case(
    users: FakeUserRepository | None = None,
    uow: FakeUoW | None = None,
) -> tuple[RegisterUserUseCase, FakeUserRepository, FakeUoW]:
    users = users or FakeUserRepository()
    uow = uow or FakeUoW()
    return RegisterUserUseCase(user_repo=users, uow=uow), users, uow


def _seed_user(repo: FakeUserRepository, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    repo.users[user.id] = user
    return user


async def test_register_creates_new_user() -> None:
    use_case, repo, uow = _make_use_case()

    response = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert response.telegram_id == 12345
    assert response.is_banned is False
    assert response.is_admin is False
    assert uow.committed is True
    assert len(repo.users) == 1
    created = next(iter(repo.users.values()))
    assert created.referred_by_user_id is None


async def test_register_is_idempotent() -> None:
    use_case, repo, uow = _make_use_case()

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    uow.committed = False
    second = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert first.id == second.id
    assert len(repo.users) == 1
    assert uow.committed is False


async def test_register_with_valid_referrer_telegram_id_links() -> None:
    use_case, repo, _ = _make_use_case()
    inviter = _seed_user(repo, 111)

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=inviter.telegram_id.value,
        )
    )

    referee = repo.users[UserId(response.id)]
    assert referee.referred_by_user_id == inviter.id


async def test_register_with_unknown_referrer_telegram_id_succeeds_no_link() -> None:
    use_case, repo, _ = _make_use_case()

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=999999999,
        )
    )

    created = repo.users[UserId(response.id)]
    assert created.referred_by_user_id is None


async def test_register_with_self_referral_silently_drops_link() -> None:
    use_case, repo, _ = _make_use_case()

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=12345,
        )
    )

    created = repo.users[UserId(response.id)]
    assert created.referred_by_user_id is None


async def test_register_with_invalid_referrer_id_silently_drops_link() -> None:
    use_case, repo, _ = _make_use_case()

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=-1,  # TelegramId rejects non-positive values
        )
    )

    created = repo.users[UserId(response.id)]
    assert created.referred_by_user_id is None


async def test_returning_user_with_referrer_payload_ignores_it() -> None:
    use_case, repo, _ = _make_use_case()
    inviter = _seed_user(repo, 111)

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    second = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=inviter.telegram_id.value,
        )
    )

    assert first.id == second.id
    returning = repo.users[UserId(second.id)]
    assert returning.referred_by_user_id is None

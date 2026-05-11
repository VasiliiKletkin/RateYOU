from dataclasses import dataclass, field
from uuid import UUID

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId


@dataclass
class FakeUserRepository:
    users: dict[UUID, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id.value] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id.value)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        for u in self.users.values():
            if u.telegram_id == telegram_id:
                return u
        return None

    async def update(self, user: User) -> None:
        self.users[user.id.value] = user


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


async def test_register_creates_new_user() -> None:
    repo = FakeUserRepository()
    uow = FakeUoW()
    use_case = RegisterUserUseCase(user_repo=repo, uow=uow)

    response = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert response.telegram_id == 12345
    assert response.is_banned is False
    assert response.is_admin is False
    assert uow.committed is True
    assert len(repo.users) == 1


async def test_register_is_idempotent() -> None:
    repo = FakeUserRepository()
    uow = FakeUoW()
    use_case = RegisterUserUseCase(user_repo=repo, uow=uow)

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    uow.committed = False  # reset so we can detect a second commit
    second = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert first.id == second.id
    assert len(repo.users) == 1
    assert uow.committed is False  # no write path on idempotent call

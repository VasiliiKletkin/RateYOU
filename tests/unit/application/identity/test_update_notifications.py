from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.application.identity.update_notifications import UpdateNotificationsUseCase
from src.domain.identity.entities import User
from src.domain.identity.exceptions import UserNotFound
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId


@dataclass
class FakeUserRepository:
    users: dict[UserId, User] = field(default_factory=dict)
    updates: int = 0

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def update(self, user: User) -> None:
        self.users[user.id] = user
        self.updates += 1

    # Unused-but-required:
    async def add(self, user: User) -> None: ...
    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None: ...
    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return []


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _seed() -> tuple[UpdateNotificationsUseCase, FakeUserRepository, FakeUoW, User]:
    user = User.register(TelegramId(555), datetime.now(UTC))
    repo = FakeUserRepository(users={user.id: user})
    uow = FakeUoW()
    return UpdateNotificationsUseCase(user_repo=repo, uow=uow), repo, uow, user


async def test_notifications_are_on_by_default() -> None:
    _, _, _, user = _seed()

    assert user.notifications_enabled is True


async def test_disabling_persists_and_commits() -> None:
    use_case, repo, uow, user = _seed()

    response = await use_case.execute(user.id.value, enabled=False)

    assert response.notifications_enabled is False
    assert repo.users[user.id].notifications_enabled is False
    assert uow.committed is True


async def test_setting_the_same_value_writes_nothing() -> None:
    """/settings re-renders often; an unchanged toggle mustn't hit the DB."""
    use_case, repo, uow, user = _seed()

    response = await use_case.execute(user.id.value, enabled=True)

    assert response.notifications_enabled is True
    assert repo.updates == 0
    assert uow.committed is False


async def test_unknown_user_raises() -> None:
    use_case, _, _, _ = _seed()

    with pytest.raises(UserNotFound):
        await use_case.execute(uuid4(), enabled=False)

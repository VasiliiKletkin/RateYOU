from typing import Protocol

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId


class IUserRepository(Protocol):
    """Persistence interface for the User aggregate.

    Implemented by infrastructure/db/repositories/user.UserRepository.
    """

    async def add(self, user: User) -> None: ...

    async def get_by_id(self, user_id: UserId) -> User | None: ...

    async def get_by_telegram_id(
        self, telegram_id: TelegramId
    ) -> User | None: ...

    async def count_referees_for(self, referrer_id: UserId) -> int: ...

    async def update(self, user: User) -> None: ...

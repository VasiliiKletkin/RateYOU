from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest, UserResponse
from src.domain.identity.entities import User
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.uow import UnitOfWork


@dataclass
class RegisterUserUseCase:
    """Idempotent: if a user with this telegram_id already exists, return them.

    Called on /start. Always returns a valid user view, regardless of whether
    they were just created or already existed.
    """

    user_repo: IUserRepository
    uow: UnitOfWork

    async def execute(self, request: RegisterUserRequest) -> UserResponse:
        telegram_id = TelegramId(request.telegram_id)

        existing = await self.user_repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            return _to_response(existing)

        user = User.register(telegram_id=telegram_id, now=datetime.now(UTC))
        await self.user_repo.add(user)
        await self.uow.commit()
        return _to_response(user)


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id.value,
        telegram_id=user.telegram_id.value,
        is_banned=user.is_banned,
        is_admin=user.is_admin,
    )

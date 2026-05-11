from dataclasses import dataclass

from src.application.identity.dto import UserResponse
from src.domain.identity.exceptions import UserNotFound
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import TelegramId


@dataclass
class GetUserByTelegramIdUseCase:
    user_repo: IUserRepository

    async def execute(self, telegram_id: int) -> UserResponse:
        user = await self.user_repo.get_by_telegram_id(TelegramId(telegram_id))
        if user is None:
            raise UserNotFound(f"No user with telegram_id={telegram_id}")
        return UserResponse(
            id=user.id.value,
            telegram_id=user.telegram_id.value,
            is_banned=user.is_banned,
            is_admin=user.is_admin,
        )

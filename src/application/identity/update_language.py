from dataclasses import dataclass
from uuid import UUID

from src.application.identity.dto import UserResponse
from src.domain.identity.exceptions import UserNotFound
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import Language
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class UpdateUserLanguageUseCase:
    """Explicit user-driven language change (e.g. via /settings).

    Separate from RegisterUserUseCase's auto-update so the intent is
    unambiguous — manual choices shouldn't get overwritten on the next
    Telegram update just because the client locale still says English.
    """

    user_repo: IUserRepository
    uow: UnitOfWork

    async def execute(self, user_id: UUID, language: Language) -> UserResponse:
        user = await self.user_repo.get_by_id(UserId(user_id))
        if user is None:
            raise UserNotFound(f"User {user_id} not found")
        if user.language != language:
            user.change_language(language)
            await self.user_repo.update(user)
            await self.uow.commit()
        return UserResponse(
            id=user.id.value,
            telegram_id=user.telegram_id.value,
            is_banned=user.is_banned,
            is_admin=user.is_admin,
            language=user.language,
        )

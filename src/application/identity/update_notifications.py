from dataclasses import dataclass
from uuid import UUID

from src.application.identity.dto import UserResponse
from src.domain.identity.exceptions import UserNotFound
from src.domain.identity.repositories import IUserRepository
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class UpdateNotificationsUseCase:
    """Turns bot-initiated broadcasts on or off for one user (/settings)."""

    user_repo: IUserRepository
    uow: UnitOfWork

    async def execute(self, user_id: UUID, enabled: bool) -> UserResponse:
        user = await self.user_repo.get_by_id(UserId(user_id))
        if user is None:
            raise UserNotFound(f"User {user_id} not found")
        # Skip the write when nothing changes — /settings re-renders often.
        if user.notifications_enabled != enabled:
            user.set_notifications(enabled)
            await self.user_repo.update(user)
            await self.uow.commit()
        return UserResponse(
            id=user.id.value,
            telegram_id=user.telegram_id.value,
            is_banned=user.is_banned,
            is_admin=user.is_admin,
            language=user.language,
            notifications_enabled=user.notifications_enabled,
        )

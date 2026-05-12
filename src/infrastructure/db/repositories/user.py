from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.identity import orm_to_user, user_to_orm
from src.infrastructure.db.models.identity import UserORM


@dataclass
class UserRepository:
    """Concrete IUserRepository backed by SQLAlchemy AsyncSession."""

    session: AsyncSession

    async def add(self, user: User) -> None:
        self.session.add(user_to_orm(user))
        await self.session.flush()

    async def get_by_id(self, user_id: UserId) -> User | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.id == user_id.value)
        )
        orm = result.scalar_one_or_none()
        return orm_to_user(orm) if orm is not None else None

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.telegram_id == telegram_id.value)
        )
        orm = result.scalar_one_or_none()
        return orm_to_user(orm) if orm is not None else None

    async def update(self, user: User) -> None:
        existing = await self.session.get(UserORM, user.id.value)
        if existing is None:
            raise ValueError(f"User {user.id.value} not found for update")
        existing.role = user.role.value
        existing.is_banned = user.is_banned
        existing.ban_reason = user.ban_reason
        existing.banned_at = user.banned_at
        existing.language = user.language
        await self.session.flush()

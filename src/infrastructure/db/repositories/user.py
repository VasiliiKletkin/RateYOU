from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.identity import UserORM


@dataclass
class UserRepository:
    """Concrete IUserRepository backed by SQLAlchemy AsyncSession."""

    session: AsyncSession

    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        """Batch load — the broadcast needs telegram_id/language for many users."""
        if not user_ids:
            return []
        result = await self.session.execute(
            select(UserORM).where(UserORM.id.in_([uid.value for uid in user_ids]))
        )
        return [
            User(
                id=UserId(orm.id),
                telegram_id=TelegramId(orm.telegram_id),
                username=orm.username,
                notifications_enabled=orm.notifications_enabled,
                role=orm.role,
                is_banned=orm.is_banned,
                ban_reason=orm.ban_reason,
                banned_at=orm.banned_at,
                language=orm.language,
                created_at=orm.created_at,
            )
            for orm in result.scalars()
        ]

    async def add(self, user: User) -> None:
        self.session.add(
            UserORM(
                id=user.id.value,
                telegram_id=user.telegram_id.value,
                username=user.username,
                notifications_enabled=user.notifications_enabled,
                role=user.role,
                is_banned=user.is_banned,
                ban_reason=user.ban_reason,
                banned_at=user.banned_at,
                language=user.language,
                created_at=user.created_at,
            )
        )
        await self.session.flush()

    async def get_by_id(self, user_id: UserId) -> User | None:
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id.value))
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return User(
            id=UserId(orm.id),
            telegram_id=TelegramId(orm.telegram_id),
            username=orm.username,
            notifications_enabled=orm.notifications_enabled,
            role=orm.role,
            is_banned=orm.is_banned,
            ban_reason=orm.ban_reason,
            banned_at=orm.banned_at,
            language=orm.language,
            created_at=orm.created_at,
        )

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.telegram_id == telegram_id.value)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return User(
            id=UserId(orm.id),
            telegram_id=TelegramId(orm.telegram_id),
            username=orm.username,
            notifications_enabled=orm.notifications_enabled,
            role=orm.role,
            is_banned=orm.is_banned,
            ban_reason=orm.ban_reason,
            banned_at=orm.banned_at,
            language=orm.language,
            created_at=orm.created_at,
        )

    async def update(self, user: User) -> None:
        existing = await self.session.get(UserORM, user.id.value)
        if existing is None:
            raise ValueError(f"User {user.id.value} not found for update")
        existing.username = user.username
        existing.notifications_enabled = user.notifications_enabled
        existing.role = user.role
        existing.is_banned = user.is_banned
        existing.ban_reason = user.ban_reason
        existing.banned_at = user.banned_at
        existing.language = user.language
        await self.session.flush()

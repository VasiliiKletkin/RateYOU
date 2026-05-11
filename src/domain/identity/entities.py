from dataclasses import dataclass
from datetime import datetime

from src.domain.identity.exceptions import InvalidBanReason, UserIsBanned
from src.domain.identity.value_objects import Role, TelegramId
from src.domain.shared.identifiers import UserId


@dataclass
class User:
    """Aggregate root of the Identity context.

    Models who can act in the system. Profile data (photos, bio, etc.)
    lives in the Profile bounded context, not here.
    """

    id: UserId
    telegram_id: TelegramId
    created_at: datetime
    role: Role = Role.USER
    is_banned: bool = False
    ban_reason: str | None = None
    banned_at: datetime | None = None

    @classmethod
    def register(cls, telegram_id: TelegramId, now: datetime) -> "User":
        return cls(
            id=UserId.new(),
            telegram_id=telegram_id,
            created_at=now,
        )

    def ban(self, reason: str, now: datetime) -> None:
        if not reason.strip():
            raise InvalidBanReason("Ban reason cannot be empty")
        self.is_banned = True
        self.ban_reason = reason.strip()
        self.banned_at = now

    def unban(self) -> None:
        self.is_banned = False
        self.ban_reason = None
        self.banned_at = None

    def ensure_active(self) -> None:
        if self.is_banned:
            raise UserIsBanned(f"User {self.id.value} is banned: {self.ban_reason}")

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

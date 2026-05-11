from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RegisterUserRequest:
    telegram_id: int


@dataclass(frozen=True, slots=True)
class UserResponse:
    id: UUID
    telegram_id: int
    is_banned: bool
    is_admin: bool

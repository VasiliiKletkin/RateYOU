from dataclasses import dataclass
from uuid import UUID

from src.domain.identity.value_objects import Language


@dataclass(frozen=True, slots=True)
class RegisterUserRequest:
    telegram_id: int
    # Normalised by the presentation layer (`normalize_language`) before
    # reaching the use case. `None` means "leave the user's stored language
    # untouched" — handy for callers that don't have a Telegram update.
    language: Language | None = None
    # Optional referrer Telegram ID parsed from the `/start <id>` deep-link
    # payload. The use case silently ignores values that don't match a known
    # user or that point at the new user themselves; registration always
    # succeeds.
    referrer_telegram_id: int | None = None


@dataclass(frozen=True, slots=True)
class UserResponse:
    id: UUID
    telegram_id: int
    is_banned: bool
    is_admin: bool
    language: Language

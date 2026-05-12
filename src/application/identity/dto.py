from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RegisterUserRequest:
    telegram_id: int
    # Normalised by the presentation layer (`normalize_language`) before
    # reaching the use case. `None` means "leave the user's stored language
    # untouched" — handy for callers that don't have a Telegram update.
    language: str | None = None
    # Optional 8-char base62 referral code from `/start ref_<code>` payload.
    # The use case silently ignores malformed codes, codes that don't match
    # any user, and self-referral; the registration always succeeds.
    referral_code: str | None = None


@dataclass(frozen=True, slots=True)
class UserResponse:
    id: UUID
    telegram_id: int
    is_banned: bool
    is_admin: bool
    language: str

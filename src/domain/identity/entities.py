from dataclasses import dataclass
from datetime import datetime

from src.domain.identity.exceptions import InvalidBanReason, UserIsBanned
from src.domain.identity.value_objects import Language, Role, TelegramId
from src.domain.shared.identifiers import UserId


def normalize_username(raw: str | None) -> str | None:
    """Canonicalises a Telegram @username: no leading '@', blanks become None.

    Telegram itself sends the handle without '@', but callers may pass either
    form; storing one shape keeps generated t.me links predictable.
    """
    if raw is None:
        return None
    cleaned = raw.strip().lstrip("@")
    return cleaned or None


@dataclass
class User:
    """Aggregate root of the Identity context.

    Models who can act in the system. Profile data (photos, bio, etc.)
    lives in the Profile bounded context, not here. Who-invited-whom is
    owned by the Referral context — the `referrals` table is the single
    source of truth for that link.

    The user's own referral handle is their `telegram_id` — shared via
    `/refer` as part of the start link.
    """

    id: UserId
    telegram_id: TelegramId
    created_at: datetime
    # Cached Telegram handle without the leading '@'. Optional — a large share
    # of accounts have none. Refreshed on /start since users can change or
    # drop it at any time; used to let raters be contacted from /my_ratings.
    username: str | None = None
    # Opt-out for bot-initiated broadcasts (e.g. "new profiles appeared").
    # Only gates outbound nudges — replies to the user's own actions and
    # notifications they directly caused are never suppressed by it.
    notifications_enabled: bool = True
    role: Role = Role.USER
    is_banned: bool = False
    ban_reason: str | None = None
    banned_at: datetime | None = None
    # Normalised by the presentation layer to one of the bot's supported
    # locales (ISO 639-1 short code); kept on the entity so we can
    # localise outgoing notifications (rating notifications, etc.) without
    # an active i18n context from a Telegram update.
    language: Language = Language.EN

    @classmethod
    def register(
        cls,
        telegram_id: TelegramId,
        now: datetime,
        language: Language = Language.EN,
        username: str | None = None,
        role: Role = Role.USER,
    ) -> "User":
        return cls(
            id=UserId.new(),
            telegram_id=telegram_id,
            username=normalize_username(username),
            language=language,
            role=role,
            created_at=now,
        )

    def change_language(self, language: Language) -> None:
        self.language = language

    def set_username(self, username: str | None) -> None:
        """Refreshes the cached handle. Idempotent — safe to call on every /start."""
        self.username = normalize_username(username)

    def set_notifications(self, enabled: bool) -> None:
        self.notifications_enabled = enabled

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

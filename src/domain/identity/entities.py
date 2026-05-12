from dataclasses import dataclass
from datetime import datetime

from src.domain.identity.exceptions import InvalidBanReason, UserIsBanned
from src.domain.identity.value_objects import ReferralCode, Role, TelegramId
from src.domain.shared.identifiers import UserId


@dataclass
class User:
    """Aggregate root of the Identity context.

    Models who can act in the system. Profile data (photos, bio, etc.)
    lives in the Profile bounded context, not here.

    `referral_code` is issued once at registration and never rotated — it's
    the user's permanent share token. `referred_by_user_id` is set ONLY at
    registration time (from a `/start ref_<code>` deep link) and is treated
    as immutable thereafter — the Referral bounded context relies on this
    to prevent retroactive referrer-switching.
    """

    id: UserId
    telegram_id: TelegramId
    created_at: datetime
    referral_code: ReferralCode
    referred_by_user_id: UserId | None = None
    role: Role = Role.USER
    is_banned: bool = False
    ban_reason: str | None = None
    banned_at: datetime | None = None
    # ISO 639-1 short code. Normalised by the presentation layer to one of
    # the bot's supported locales; kept on the entity so we can localise
    # outgoing notifications (rating notifications, etc.) without an active
    # i18n context from a Telegram update.
    language: str = "en"

    @classmethod
    def register(
        cls,
        telegram_id: TelegramId,
        now: datetime,
        language: str = "en",
        referred_by: UserId | None = None,
    ) -> "User":
        return cls(
            id=UserId.new(),
            telegram_id=telegram_id,
            language=language,
            created_at=now,
            referral_code=ReferralCode.new(),
            referred_by_user_id=referred_by,
        )

    def change_language(self, language: str) -> None:
        self.language = language

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

import secrets
import string
from dataclasses import dataclass
from enum import StrEnum

from src.domain.identity.exceptions import InvalidReferralCode

REFERRAL_CODE_LENGTH = 8
REFERRAL_CODE_ALPHABET = string.ascii_letters + string.digits  # base62


@dataclass(frozen=True, slots=True)
class TelegramId:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Telegram ID must be positive, got {self.value}")


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class ReferralCode:
    """8-char base62 code embedded in a user's referral deep link.

    Issued once at registration and never rotated. The bot's invite link is
    `https://t.me/<bot>?start=ref_<code>` — code is short enough to share
    verbally yet wide enough (62^8 ~ 218 trillion) for collisions to be
    irrelevant at any plausible user scale.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != REFERRAL_CODE_LENGTH:
            raise InvalidReferralCode(
                f"Referral code must be {REFERRAL_CODE_LENGTH} chars, "
                f"got {len(self.value)}"
            )
        if any(c not in REFERRAL_CODE_ALPHABET for c in self.value):
            raise InvalidReferralCode(
                f"Referral code contains invalid characters: {self.value!r}"
            )

    @classmethod
    def new(cls) -> "ReferralCode":
        return cls(
            "".join(
                secrets.choice(REFERRAL_CODE_ALPHABET)
                for _ in range(REFERRAL_CODE_LENGTH)
            )
        )

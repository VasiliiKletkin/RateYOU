import re
from dataclasses import dataclass
from enum import StrEnum

from src.domain.identity.exceptions import InvalidAcquisitionSource

# Telegram caps the `/start` deep-link payload at 64 characters and allows
# only these, so a tag that doesn't match could never have arrived from a
# real link.
_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True, slots=True)
class TelegramId:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Telegram ID must be positive, got {self.value}")


@dataclass(frozen=True, slots=True)
class AcquisitionSource:
    """Where a user came from, taken from their `/start` payload.

    Lowercased on the way in: `Habr` and `habr` are the same channel and
    must not split into two rows in the funnel report.
    """

    value: str

    def __post_init__(self) -> None:
        if not _SOURCE_PATTERN.match(self.value):
            raise InvalidAcquisitionSource(f"Invalid acquisition source: {self.value!r}")
        object.__setattr__(self, "value", self.value.lower())


class Role(StrEnum):
    """What a user is in the system.

    SEED marks seeded content rather than a person: nothing is ever
    delivered to its ``telegram_id``, but its profile still takes part in
    discovery so early real users have something to rate.
    """

    USER = "user"
    ADMIN = "admin"
    SEED = "seed"


class Language(StrEnum):
    """User-facing locales supported by the bot.

    Values are ISO 639-1 codes; member names follow the same. Stored on
    ``User.language`` and used as the i18n locale identifier (StrEnum is a
    ``str`` subclass, so it passes through unchanged to aiogram's I18n).
    """

    EN = "en"
    RU = "ru"
    ES = "es"
    PT = "pt"
    DE = "de"
    FR = "fr"
    IT = "it"
    TR = "tr"
    UK = "uk"
    PL = "pl"
    AR = "ar"
    FA = "fa"
    ID = "id"
    VI = "vi"
    ZH = "zh"
    HI = "hi"
    BN = "bn"
    AM = "am"
    UZ = "uz"
    KO = "ko"
    JA = "ja"
    TH = "th"

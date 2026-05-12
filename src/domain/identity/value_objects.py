from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class TelegramId:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Telegram ID must be positive, got {self.value}")


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


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

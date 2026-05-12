import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n, I18nMiddleware

log = logging.getLogger(__name__)

# locales/ at the project root, sibling to src/.
LOCALES_DIR = Path(__file__).resolve().parents[3] / "locales"
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "en",
    "ru",
    "es",
    "pt",
    "de",
    "fr",
    "it",
    "tr",
    "uk",
    "pl",
    "ar",
    "fa",
    "id",
    "vi",
    "zh",
    "hi",
    "bn",
    "am",
    "uz",
    "ko",
    "ja",
    "th",
)
DEFAULT_LANGUAGE = "en"

# Each supported locale's display name in its own script — used as button
# labels in the /settings language picker so a Russian user sees "Русский"
# regardless of their current UI language. Order matches SUPPORTED_LANGUAGES.
LANGUAGE_NATIVE_NAMES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
    "es": "Español",
    "pt": "Português",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "tr": "Türkçe",
    "uk": "Українська",
    "pl": "Polski",
    "ar": "العربية",
    "fa": "فارسی",
    "id": "Bahasa Indonesia",
    "vi": "Tiếng Việt",
    "zh": "中文",
    "hi": "हिन्दी",
    "bn": "বাংলা",
    "am": "አማርኛ",
    "uz": "Oʻzbekcha",  # noqa: RUF001 — U+02BB is the canonical Uzbek apostrophe
    "ko": "한국어",
    "ja": "日本語",
    "th": "ไทย",
}


def native_name(language: str) -> str:
    """Returns the language's native label, falling back to the code itself."""
    return LANGUAGE_NATIVE_NAMES.get(language, language)


i18n = I18n(
    path=LOCALES_DIR,
    default_locale=DEFAULT_LANGUAGE,
    domain="messages",
)


def normalize_language(raw: str | None) -> str:
    """Map a Telegram `language_code` (e.g. 'ru', 'ru-RU') to a supported one.

    Strips the region suffix and lowercases. Unsupported codes (or None) fall
    back to DEFAULT_LANGUAGE so callers always get a valid locale string.
    """
    if not raw:
        return DEFAULT_LANGUAGE
    primary = raw.split("-")[0].lower()
    return primary if primary in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


class UserLanguageI18nMiddleware(I18nMiddleware):
    """Picks the locale from Telegram's `from_user.language_code`.

    Delegates the actual normalisation to `normalize_language` so the
    register-user flow can store the same canonical code on `User.language`.
    """

    async def get_locale(
        self,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> str:
        tg_user = getattr(event, "from_user", None)
        raw = getattr(tg_user, "language_code", None) if tg_user else None
        chosen = normalize_language(raw)
        log.info(
            "i18n: tg_user=%s raw=%r → %s",
            getattr(tg_user, "id", None),
            raw,
            chosen,
        )
        return chosen

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        return await super().__call__(handler, event, data)

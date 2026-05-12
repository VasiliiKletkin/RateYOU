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

i18n = I18n(
    path=LOCALES_DIR,
    default_locale=DEFAULT_LANGUAGE,
    domain="messages",
)


class UserLanguageI18nMiddleware(I18nMiddleware):
    """Picks the locale from Telegram's `from_user.language_code`.

    Telegram sends ISO codes like 'en', 'ru', 'ru-RU'. We strip the region
    suffix and fall back to DEFAULT_LANGUAGE if the language isn't
    supported. Later, a User-stored preference can override this.
    """

    async def get_locale(
        self,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> str:
        tg_user = getattr(event, "from_user", None)
        raw = getattr(tg_user, "language_code", None) if tg_user else None
        if tg_user is None or raw is None:
            log.info("i18n: no language_code, using default=%s", DEFAULT_LANGUAGE)
            return DEFAULT_LANGUAGE
        primary = raw.split("-")[0].lower()
        chosen = primary if primary in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        log.info("i18n: tg_user=%s raw=%r → %s", tg_user.id, raw, chosen)
        return chosen

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        return await super().__call__(handler, event, data)

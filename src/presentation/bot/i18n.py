import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n, I18nMiddleware
from dishka import AsyncContainer

from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import Language, TelegramId

log = logging.getLogger(__name__)

# locales/ at the project root, sibling to src/.
LOCALES_DIR = Path(__file__).resolve().parents[3] / "locales"
DEFAULT_LANGUAGE: Language = Language.EN

# Each supported locale's display name in its own script — used as button
# labels in the /settings language picker so a Russian user sees "Русский"
# regardless of their current UI language.
LANGUAGE_NATIVE_NAMES: dict[Language, str] = {
    Language.EN: "English",
    Language.RU: "Русский",
    Language.ES: "Español",
    Language.PT: "Português",
    Language.DE: "Deutsch",
    Language.FR: "Français",
    Language.IT: "Italiano",
    Language.TR: "Türkçe",
    Language.UK: "Українська",
    Language.PL: "Polski",
    Language.AR: "العربية",
    Language.FA: "فارسی",
    Language.ID: "Bahasa Indonesia",
    Language.VI: "Tiếng Việt",
    Language.ZH: "中文",
    Language.HI: "हिन्दी",
    Language.BN: "বাংলা",
    Language.AM: "አማርኛ",
    Language.UZ: "Oʻzbekcha",  # noqa: RUF001 — U+02BB is the canonical Uzbek apostrophe
    Language.KO: "한국어",
    Language.JA: "日本語",
    Language.TH: "ไทย",
}


def native_name(language: Language) -> str:
    """Returns the language's native label, falling back to the code itself."""
    return LANGUAGE_NATIVE_NAMES.get(language, language.value)


i18n = I18n(
    path=LOCALES_DIR,
    default_locale=DEFAULT_LANGUAGE.value,
    domain="messages",
)


def normalize_language(raw: str | None) -> Language:
    """Map a Telegram ``language_code`` (e.g. 'ru', 'ru-RU') to a Language.

    Strips the region suffix and lowercases. Unsupported codes (or None) fall
    back to ``DEFAULT_LANGUAGE`` so callers always get a valid enum member.
    """
    if not raw:
        return DEFAULT_LANGUAGE
    primary = raw.split("-")[0].lower()
    try:
        return Language(primary)
    except ValueError:
        return DEFAULT_LANGUAGE


class UserLanguageI18nMiddleware(I18nMiddleware):
    """Picks the locale from `User.language` stored in the DB.

    The user's stored language is authoritative: it's set on first /start
    from Telegram's `language_code` and then only changed via /settings.
    Subsequent updates ignore Telegram's client locale and follow whatever
    the user picked.

    Fallback chain:
      1. `User.language` looked up by `telegram_id` (request-scope container)
      2. Telegram's `from_user.language_code`, normalised
      3. `DEFAULT_LANGUAGE`
    """

    async def get_locale(
        self,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> str:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return DEFAULT_LANGUAGE.value

        container: AsyncContainer | None = data.get("dishka_container")
        if container is not None:
            try:
                user_repo = await container.get(IUserRepository)
                user = await user_repo.get_by_telegram_id(TelegramId(tg_user.id))
            except Exception:
                # DB unreachable / repo not yet wired — fall back rather
                # than 500-ing every update.
                log.warning(
                    "i18n: stored language lookup failed; falling back to Telegram code",
                    exc_info=True,
                )
                user = None
            if user is not None:
                stored = user.language
                log.info("i18n: tg_user=%s → stored %s", tg_user.id, stored.value)
                return str(stored.value)

        raw = getattr(tg_user, "language_code", None)
        chosen = normalize_language(raw)
        log.info(
            "i18n: tg_user=%s no stored language, telegram=%r → %s",
            tg_user.id,
            raw,
            chosen.value,
        )
        return chosen.value

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        return await super().__call__(handler, event, data)

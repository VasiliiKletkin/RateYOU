from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.discovery.search_preferences import GetSearchPreferencesUseCase
from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.presentation.bot.handlers.search_location import prompt_for_search_city
from src.presentation.bot.i18n import normalize_language

router = Router(name="start")


@router.message(CommandStart())
async def on_start(
    message: Message,
    state: FSMContext,
    command: CommandObject,
    register_user: FromDishka[RegisterUserUseCase],
    get_prefs: FromDishka[GetSearchPreferencesUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
            referrer_telegram_id=_extract_referrer_telegram_id(command.args),
            # /start is the one handler every user passes through, so it is
            # where the cached @username gets (re)captured.
            username=message.from_user.username,
        )
    )
    prefs = await get_prefs.execute(user.id)

    if prefs.has_location:
        await message.answer(
            _("<b>Welcome back!</b>\nSend /feed to rate profiles, or /create to set up your own.")
        )
        return

    # No search area yet: browsing is one step away — no profile required.
    await message.answer(
        _(
            "<b>Welcome to RateYou!</b>\n"
            "Set where you want to browse and you can start rating right away. "
            "Want to be rated too? Send /create to make your own profile."
        )
    )
    await prompt_for_search_city(message, state)


def _extract_referrer_telegram_id(payload: str | None) -> int | None:
    """Parses a `/start <telegram_id>` payload.

    Returns the integer ID if the payload is a positive decimal number.
    Returns None for missing / malformed payloads — the use case is then
    free to register the user without a referrer link.
    """
    if not payload:
        return None
    try:
        value = int(payload)
    except ValueError:
        return None
    return value if value > 0 else None

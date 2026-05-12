from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.presentation.bot.i18n import normalize_language

router = Router(name="start")


@router.message(CommandStart())
async def on_start(
    message: Message,
    command: CommandObject,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
            referrer_telegram_id=_extract_referrer_telegram_id(command.args),
        )
    )
    profile = await get_my_profile.execute(user.id)

    if profile is None:
        await message.answer(
            _(
                "<b>Welcome to RateYou!</b>\n"
                "You don't have a profile yet - send /create to make one."
            )
        )
    else:
        await message.answer(
            _("<b>Welcome back, {name}!</b>\nSend /feed to rate other profiles.").format(
                name=profile.name
            )
        )


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

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

_REFERRAL_PAYLOAD_PREFIX = "ref_"


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
            referral_code=_extract_referral_code(command.args),
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


def _extract_referral_code(payload: str | None) -> str | None:
    """Pulls the 8-char code out of a `ref_<code>` start payload.

    Returns None if the payload is missing, doesn't carry the `ref_` prefix,
    or has the wrong length. Validation of the alphabet is deferred to the
    `ReferralCode` value object in the use case.
    """
    if not payload or not payload.startswith(_REFERRAL_PAYLOAD_PREFIX):
        return None
    return payload.removeprefix(_REFERRAL_PAYLOAD_PREFIX) or None

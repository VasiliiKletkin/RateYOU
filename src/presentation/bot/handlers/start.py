from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.get_profile import GetMyProfileUseCase

router = Router(name="start")


@router.message(CommandStart())
async def on_start(
    message: Message,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(telegram_id=message.from_user.id)
    )
    profile = await get_my_profile.execute(user.id)

    if profile is None:
        await message.answer(
            _(
                "<b>Welcome to RateMe!</b>\n"
                "You don't have a profile yet - send /create to make one."
            )
        )
    else:
        await message.answer(
            _("<b>Welcome back, {name}!</b>\nSend /feed to rate other profiles.").format(
                name=profile.name
            )
        )

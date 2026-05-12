from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.dto import EditProfileRequest
from src.application.profile.edit_profile import EditProfileUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.domain.profile.exceptions import ProfileNotFound
from src.presentation.bot.keyboards import gender_preference_keyboard

_SETTINGS_PREFIX = "setpref"

router = Router(name="settings")


def _format_preference(value: str) -> str:
    # Mirror of the button labels so the "current value" line uses the same
    # wording the user just saw.
    if value == "male":
        return _("♂️ Men")
    if value == "female":
        return _("♀️ Women")
    return _("👥 Everyone")


@router.message(Command("settings"))
async def cmd_settings(
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
        await message.answer(_("No profile yet. Use /create first."))
        return

    await message.answer(
        _(
            "<b>Settings</b>\n"
            "Who you want to rate: {current}\n\n"
            "Pick a new preference:"
        ).format(current=_format_preference(profile.gender_preference)),
        reply_markup=gender_preference_keyboard(prefix=_SETTINGS_PREFIX),
    )


@router.callback_query(F.data.startswith(f"{_SETTINGS_PREFIX}:"))
async def on_set_preference(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
    edit_profile: FromDishka[EditProfileUseCase],
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    preference = callback.data.removeprefix(f"{_SETTINGS_PREFIX}:")
    if preference not in ("male", "female", "any"):
        await callback.answer(_("Invalid choice"))
        return

    user = await register_user.execute(
        RegisterUserRequest(telegram_id=callback.from_user.id)
    )
    profile = await get_my_profile.execute(user.id)
    if profile is None:
        await callback.answer(_("No profile yet. Use /create first."))
        return

    try:
        await edit_profile.execute(
            EditProfileRequest(
                profile_id=profile.id,
                gender_preference=preference,
            )
        )
    except ProfileNotFound:
        await callback.answer(_("Profile not found."))
        return

    await callback.answer(_("Updated"))
    if isinstance(callback.message, Message):
        await callback.message.answer(
            _("Preference saved: {current}").format(
                current=_format_preference(preference)
            )
        )

from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.discovery.dto import SearchPreferencesResponse
from src.application.discovery.search_preferences import (
    GetSearchPreferencesUseCase,
    UpdateGenderPreferenceUseCase,
    UpdateMinRatingUseCase,
)
from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.domain.discovery.exceptions import InvalidMinRating
from src.presentation.bot.keyboards import settings_keyboard

_GENDER_PREFIX = "setpref"
_RATING_PREFIX = "setrating"

router = Router(name="settings")


def _format_gender(value: str) -> str:
    # Mirror of the button labels so the "current value" line uses the same
    # wording the user just saw.
    if value == "male":
        return _("♂️ Men")
    if value == "female":
        return _("♀️ Women")
    return _("👥 Everyone")


def _format_min_rating(value: int) -> str:
    if value <= 0:
        return _("Any")
    return f"{value}+"


def _render_body(
    prefs: SearchPreferencesResponse, *, is_premium: bool
) -> str:
    lines = [
        _("<b>Settings</b>"),
        _("Show me: {current}").format(
            current=_format_gender(prefs.gender_preference)
        ),
    ]
    if is_premium:
        lines.append(
            _("Min rating: {current}").format(
                current=_format_min_rating(prefs.min_rating)
            )
        )
    else:
        lines.append(
            _("Min rating: premium only (use /premium)")
        )
    return "\n".join(lines)


async def _refresh(
    callback: CallbackQuery,
    prefs: SearchPreferencesResponse,
    *,
    is_premium: bool,
) -> None:
    """Edit the existing /settings card so taps don't pile up messages.

    Telegram errors when the body+markup are unchanged (e.g. picking the
    current value again) — suppress that specific case quietly.
    """
    if not isinstance(callback.message, Message):
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            _render_body(prefs, is_premium=is_premium),
            reply_markup=settings_keyboard(show_min_rating=is_premium),
        )


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_profile: FromDishka[GetMyProfileUseCase],
    get_prefs: FromDishka[GetSearchPreferencesUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(telegram_id=message.from_user.id)
    )
    if (await get_my_profile.execute(user.id)) is None:
        await message.answer(_("No profile yet. Use /create first."))
        return

    prefs = await get_prefs.execute(user.id)
    is_premium = (await get_my_premium.execute(user.id)) is not None
    await message.answer(
        _render_body(prefs, is_premium=is_premium),
        reply_markup=settings_keyboard(show_min_rating=is_premium),
    )


@router.callback_query(F.data.startswith(f"{_GENDER_PREFIX}:"))
async def on_set_gender(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    update_gender: FromDishka[UpdateGenderPreferenceUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    preference = callback.data.removeprefix(f"{_GENDER_PREFIX}:")
    if preference not in ("male", "female", "any"):
        await callback.answer(_("Invalid choice"))
        return

    user = await register_user.execute(
        RegisterUserRequest(telegram_id=callback.from_user.id)
    )
    prefs = await update_gender.execute(user.id, preference)
    is_premium = (await get_my_premium.execute(user.id)) is not None
    await callback.answer(_("Updated"))
    await _refresh(callback, prefs, is_premium=is_premium)


@router.callback_query(F.data.startswith(f"{_RATING_PREFIX}:"))
async def on_set_min_rating(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    update_min_rating: FromDishka[UpdateMinRatingUseCase],
    get_prefs: FromDishka[GetSearchPreferencesUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    raw = callback.data.removeprefix(f"{_RATING_PREFIX}:")
    try:
        value = int(raw)
    except ValueError:
        await callback.answer(_("Invalid choice"))
        return

    user = await register_user.execute(
        RegisterUserRequest(telegram_id=callback.from_user.id)
    )
    is_premium = (await get_my_premium.execute(user.id)) is not None
    if not is_premium:
        # Defensive — the button is hidden for non-premium, but a stale
        # keyboard from before an expiry could still send it.
        prefs = await get_prefs.execute(user.id)
        await callback.answer(_("Premium only"), show_alert=True)
        await _refresh(callback, prefs, is_premium=is_premium)
        return

    try:
        prefs = await update_min_rating.execute(user.id, value)
    except InvalidMinRating:
        await callback.answer(_("Invalid choice"))
        return
    await callback.answer(_("Updated"))
    await _refresh(callback, prefs, is_premium=is_premium)

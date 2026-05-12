from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
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
from src.application.identity.update_language import UpdateUserLanguageUseCase
from src.application.profile.get_profile import GetMyProfileUseCase
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.domain.discovery.exceptions import InvalidMinRating
from src.presentation.bot.i18n import (
    LANGUAGE_NATIVE_NAMES,
    SUPPORTED_LANGUAGES,
    i18n,
    native_name,
    normalize_language,
)
from src.presentation.bot.keyboards import (
    gender_preference_keyboard,
    language_keyboard,
    rating_picker_keyboard,
    settings_main_keyboard,
)

# Picker action callbacks. They're plain strings (no payload) — they only
# swap the keyboard, not the value.
_OPEN_GENDER = "openpref"
_OPEN_RATING = "openrating"
_OPEN_LANGUAGE = "openlang"

# Value-setter callback prefixes. Payload is the new value.
_GENDER_PREFIX = "setpref"
_RATING_PREFIX = "setrating"
_LANGUAGE_PREFIX = "setlang"

router = Router(name="settings")


def _format_gender(value: str) -> str:
    # Mirror of the picker labels so the main button reads consistently.
    if value == "male":
        return _("♂️ Men")
    if value == "female":
        return _("♀️ Women")
    return _("👥 Everyone")


def _format_min_rating(value: int) -> str:
    if value <= 0:
        return _("Any")
    return f"{value}+"


def _main_keyboard(
    prefs: SearchPreferencesResponse, *, is_premium: bool, language: str
) -> InlineKeyboardMarkup:
    gender_label = _("👤 Show me: {current}").format(
        current=_format_gender(prefs.gender_preference)
    )
    if is_premium:
        rating_label = _("⭐ Min rating: {current}").format(
            current=_format_min_rating(prefs.min_rating)
        )
    else:
        rating_label = _("⭐ Min rating: premium only")
    language_label = _("🌐 Language: {current}").format(
        current=native_name(language)
    )
    return settings_main_keyboard(
        gender_label=gender_label,
        rating_label=rating_label,
        language_label=language_label,
        gender_action=_OPEN_GENDER,
        rating_action=_OPEN_RATING,
        language_action=_OPEN_LANGUAGE,
    )


async def _refresh_main(
    callback: CallbackQuery,
    prefs: SearchPreferencesResponse,
    *,
    is_premium: bool,
    language: str,
) -> None:
    """Restore the top-level settings view after a picker tap.

    Telegram errors when the body+markup don't change (e.g. picking the
    current value); the suppress is what keeps that quiet.
    """
    if not isinstance(callback.message, Message):
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_text(
            _("<b>Settings</b>"),
            reply_markup=_main_keyboard(
                prefs, is_premium=is_premium, language=language
            ),
        )


async def _swap_keyboard(
    callback: CallbackQuery, markup: InlineKeyboardMarkup
) -> None:
    if not isinstance(callback.message, Message):
        return
    with suppress(TelegramAPIError):
        await callback.message.edit_reply_markup(reply_markup=markup)


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
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    if (await get_my_profile.execute(user.id)) is None:
        await message.answer(_("No profile yet. Use /create first."))
        return

    prefs = await get_prefs.execute(user.id)
    is_premium = (await get_my_premium.execute(user.id)) is not None
    await message.answer(
        _("<b>Settings</b>"),
        reply_markup=_main_keyboard(
            prefs, is_premium=is_premium, language=user.language
        ),
    )


@router.callback_query(F.data == _OPEN_GENDER)
async def on_open_gender_picker(callback: CallbackQuery) -> None:
    await _swap_keyboard(
        callback, gender_preference_keyboard(prefix=_GENDER_PREFIX)
    )
    await callback.answer()


@router.callback_query(F.data == _OPEN_RATING)
async def on_open_rating_picker(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    if (await get_my_premium.execute(user.id)) is None:
        await callback.answer(_("Premium only"), show_alert=True)
        return
    await _swap_keyboard(callback, rating_picker_keyboard(prefix=_RATING_PREFIX))
    await callback.answer()


@router.callback_query(F.data == _OPEN_LANGUAGE)
async def on_open_language_picker(callback: CallbackQuery) -> None:
    await _swap_keyboard(
        callback,
        language_keyboard(
            SUPPORTED_LANGUAGES,
            LANGUAGE_NATIVE_NAMES,
            prefix=_LANGUAGE_PREFIX,
        ),
    )
    await callback.answer()


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
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    prefs = await update_gender.execute(user.id, preference)
    is_premium = (await get_my_premium.execute(user.id)) is not None
    await callback.answer(_("Updated"))
    await _refresh_main(
        callback, prefs, is_premium=is_premium, language=user.language
    )


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
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    is_premium = (await get_my_premium.execute(user.id)) is not None
    if not is_premium:
        # Defensive — the button is hidden for non-premium, but a stale
        # keyboard from before an expiry could still send it.
        prefs = await get_prefs.execute(user.id)
        await callback.answer(_("Premium only"), show_alert=True)
        await _refresh_main(
            callback, prefs, is_premium=is_premium, language=user.language
        )
        return

    try:
        prefs = await update_min_rating.execute(user.id, value)
    except InvalidMinRating:
        await callback.answer(_("Invalid choice"))
        return
    await callback.answer(_("Updated"))
    await _refresh_main(
        callback, prefs, is_premium=is_premium, language=user.language
    )


@router.callback_query(F.data.startswith(f"{_LANGUAGE_PREFIX}:"))
async def on_set_language(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    update_user_language: FromDishka[UpdateUserLanguageUseCase],
    get_prefs: FromDishka[GetSearchPreferencesUseCase],
    get_my_premium: FromDishka[GetMyPremiumUseCase],
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    chosen = callback.data.removeprefix(f"{_LANGUAGE_PREFIX}:")
    if chosen not in SUPPORTED_LANGUAGES:
        await callback.answer(_("Invalid choice"))
        return

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            # Don't overwrite the explicit pick with the Telegram code —
            # the user is choosing manually right here.
            language=None,
        )
    )
    updated = await update_user_language.execute(user.id, chosen)
    prefs = await get_prefs.execute(user.id)
    is_premium = (await get_my_premium.execute(user.id)) is not None

    # Render the confirmation in the freshly-picked locale so the refreshed
    # card matches what the user just chose.
    with i18n.use_locale(updated.language):
        await callback.answer(_("Updated"))
        await _refresh_main(
            callback, prefs, is_premium=is_premium, language=updated.language
        )

"""Set the feed's search origin without needing a profile.

The feed sorts candidates by distance from `SearchPreferences.location`.
This flow lets a brand-new user pick that origin (share location or type a
city), then drops them straight into the feed — no profile required.

Mirrors the location step of /create, but writes to SearchPreferences
instead of a half-built profile. The duplication is deliberate and small;
the two flows own different aggregates.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.discovery.get_next_profile import GetNextProfileForRatingUseCase
from src.application.discovery.search_preferences import UpdateSearchLocationUseCase
from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.domain.profile.exceptions import GeocodingUnavailable
from src.domain.profile.geocoder import IGeocoder
from src.presentation.bot.handlers.feed import show_next_or_done
from src.presentation.bot.i18n import i18n, normalize_language
from src.presentation.bot.keyboards import (
    geocode_candidates_keyboard,
    share_location_keyboard,
)
from src.presentation.bot.states import SetSearchLocation

router = Router(name="search_location")


async def prompt_for_search_city(message: Message, state: FSMContext) -> None:
    """Ask for a search area and enter the picker FSM.

    Reused by /start, /feed (when no location is set yet) and /setcity.
    """
    await state.set_state(SetSearchLocation.waiting_for_location)
    await message.answer(
        _(
            "📍 Where do you want to browse?\n"
            "Share your location, or type a city name — profiles nearest to "
            "it come first."
        ),
        reply_markup=share_location_keyboard(_("📍 Share location")),
    )


@router.message(Command("setcity"))
async def cmd_set_city(message: Message, state: FSMContext) -> None:
    await prompt_for_search_city(message, state)


@router.message(F.location, SetSearchLocation.waiting_for_location)
async def process_shared_location(
    message: Message,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    update_search_location: FromDishka[UpdateSearchLocationUseCase],
    get_next: FromDishka[GetNextProfileForRatingUseCase],
) -> None:
    if message.location is None or message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    await update_search_location.execute(
        user.id, message.location.latitude, message.location.longitude
    )
    await state.clear()
    await message.answer(
        _("✅ Search area saved."),
        reply_markup=ReplyKeyboardRemove(),
    )
    await show_next_or_done(message, user.id, get_next)


# `~F.text.startswith("/")` keeps commands out of the geocoder — a /feed
# typed mid-flow must fall through to its own handler, not be looked up as a
# city name.
@router.message(
    F.text,
    ~F.text.startswith("/"),
    SetSearchLocation.waiting_for_location,
)
async def process_typed_city(
    message: Message,
    state: FSMContext,
    geocoder: FromDishka[IGeocoder],
) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer(_("Please share a location or type a city name."))
        return

    try:
        candidates = await geocoder.geocode(query, language=i18n.current_locale)
    except GeocodingUnavailable:
        await message.answer(
            _("Couldn't look that up right now — please share your location instead.")
        )
        return

    if not candidates:
        await message.answer(_("No such place found. Check the spelling, or share your location."))
        return

    # Parked in FSM so buttons only carry an index — Telegram caps callback
    # data at 64 bytes.
    await state.update_data(
        geocode_candidates=[
            {"label": c.label, "lat": c.location.lat, "lon": c.location.lon} for c in candidates
        ]
    )
    await message.answer(
        _("Pick your city:"),
        reply_markup=geocode_candidates_keyboard([c.label for c in candidates]),
    )


@router.callback_query(
    F.data.startswith("geopick:"),
    SetSearchLocation.waiting_for_location,
)
async def process_city_picked(
    callback: CallbackQuery,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    update_search_location: FromDishka[UpdateSearchLocationUseCase],
    get_next: FromDishka[GetNextProfileForRatingUseCase],
) -> None:
    if callback.data is None or callback.from_user is None:
        await callback.answer()
        return
    candidates = (await state.get_data()).get("geocode_candidates") or []
    try:
        picked = candidates[int(callback.data.removeprefix("geopick:"))]
    except (ValueError, IndexError):
        await callback.answer(_("Invalid choice"))
        return

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    await update_search_location.execute(user.id, picked["lat"], picked["lon"])
    await state.clear()
    await callback.answer(_("✅ Search area saved."))
    if isinstance(callback.message, Message):
        await show_next_or_done(callback.message, user.id, get_next)


@router.message(SetSearchLocation.waiting_for_location)
async def process_location_invalid(message: Message) -> None:
    await message.answer(_("Please share a location or type a city name."))

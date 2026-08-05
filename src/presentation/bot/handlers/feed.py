from contextlib import suppress
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext
from dishka import FromDishka

from src.application.discovery.dto import NextProfileResponse
from src.application.discovery.get_next_profile import (
    FREE_RATINGS_WITHOUT_PROFILE,
    GetNextProfileForRatingUseCase,
)
from src.application.discovery.skip_profile import SkipProfileUseCase
from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.rating.dto import RateUserRequest
from src.application.rating.get_profile_score import GetProfileScoreUseCase
from src.application.rating.rate_user import RateUserUseCase
from src.domain.discovery.exceptions import ProfileRequiredToContinue, SearchLocationNotSet
from src.domain.identity.repositories import IUserRepository
from src.domain.rating.exceptions import CannotRateSelf, InvalidScore
from src.domain.shared.identifiers import UserId
from src.presentation.bot.i18n import i18n, normalize_language
from src.presentation.bot.keyboards import gender_preference_keyboard, rating_keyboard
from src.presentation.bot.states import SetSearchLocation

router = Router(name="feed")


async def _start_browse_onboarding(message: Message, state: FSMContext) -> None:
    """First-time setup: gender preference, then city (search_location owns it).

    Kept local to avoid a feed <-> search_location import cycle; search_location
    imports `show_next_or_done` from here.
    """
    await state.set_state(SetSearchLocation.waiting_for_gender_preference)
    await message.answer(
        _("Who would you like to rate?"),
        reply_markup=gender_preference_keyboard(),
    )


def _format_caption(profile: NextProfileResponse) -> str:
    lines = [
        f"<b>{profile.name}, {profile.age}</b>",
        f"📍 {_format_distance(profile.distance_meters)}",
    ]
    if profile.bio:
        lines.append("")
        lines.append(profile.bio)
    return "\n".join(lines)


def _format_distance(meters: int) -> str:
    """Compact distance label: '350 m' below 1 km, '5.4 km' otherwise."""
    if meters < 1_000:
        return f"{meters} m"
    return f"{meters / 1000:.1f} km"


async def show_next_or_done(
    message: Message,
    viewer_id: UUID,
    get_next: GetNextProfileForRatingUseCase,
    state: FSMContext | None = None,
) -> None:
    """Sends the viewer's next candidate, or a "come back later" note.

    Public because /create and the search-location picker both hand the user
    straight into the feed once they're set up, instead of asking them to
    type /feed.

    If the viewer has no search location yet, prompts them to set one (when
    `state` is given) rather than showing candidates.
    """
    try:
        next_profile = await get_next.execute(viewer_id)
    except SearchLocationNotSet:
        if state is not None:
            await _start_browse_onboarding(message, state)
        else:
            await message.answer(_("Set your search area first — send /setcity."))
        return
    except ProfileRequiredToContinue:
        await message.answer(
            _(
                "🔒 You've rated {count} profiles — that's the limit without a "
                "profile of your own.\n"
                "Create yours with /create to keep rating (and find out how "
                "people rate you)."
            ).format(count=FREE_RATINGS_WITHOUT_PROFILE)
        )
        return
    if next_profile is None:
        await message.answer(_("No more profiles to rate. Come back later!"))
        return

    photos = next_profile.photo_file_ids
    caption = _format_caption(next_profile)

    if len(photos) == 1:
        await message.answer_photo(
            photo=photos[0],
            caption=caption,
            reply_markup=rating_keyboard(next_profile.owner_id),
        )
        return

    # send_media_group requires 2-10 items. Caption goes on the first one
    # (Telegram convention). Rating buttons live in a sibling message because
    # media groups don't support inline keyboards.
    #
    # answer_media_group's `media` is invariant (typed as the broad union of
    # all InputMedia* types); a `list[InputMediaPhoto]` doesn't satisfy it,
    # though it does at runtime.
    media: list[InputMediaPhoto] = [
        InputMediaPhoto(media=fid, caption=caption if i == 0 else None)
        for i, fid in enumerate(photos)
    ]
    await message.answer_media_group(media=media)  # type: ignore[arg-type]
    await message.answer(
        _("Rate this profile:"),
        reply_markup=rating_keyboard(next_profile.owner_id),
    )


async def _strip_keyboard(message: Message) -> None:
    with suppress(TelegramAPIError):
        await message.edit_reply_markup(reply_markup=None)


async def _notify_rated_user(
    bot: Bot,
    user_repo: IUserRepository,
    rated_user_id: UUID,
    score: int,
) -> None:
    rated_user = await user_repo.get_by_id(UserId(rated_user_id))
    if rated_user is None or rated_user.is_banned:
        return
    # Switch the i18n contextvar to the recipient's stored language so the
    # notification reads in their locale, not the rater's.
    with i18n.use_locale(rated_user.language.value):
        text = _("⭐ Someone just rated you: {score}/10").format(score=score)
    with suppress(TelegramAPIError):
        await bot.send_message(rated_user.telegram_id.value, text)


@router.message(Command("feed"))
async def cmd_feed(
    message: Message,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    get_next: FromDishka[GetNextProfileForRatingUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    # No profile-of-your-own gate: a search location is all the feed needs,
    # and show_next_or_done prompts for it when missing.
    await show_next_or_done(message, user.id, get_next, state)


@router.callback_query(F.data.startswith("rate:"))
async def on_rate(
    callback: CallbackQuery,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    rate_user: FromDishka[RateUserUseCase],
    get_profile_score: FromDishka[GetProfileScoreUseCase],
    get_next: FromDishka[GetNextProfileForRatingUseCase],
    user_repo: FromDishka[IUserRepository],
    bot: FromDishka[Bot],
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer(_("Bad payload"))
        return
    try:
        rated_user_id = UUID(parts[1])
        score = int(parts[2])
    except ValueError:
        await callback.answer(_("Bad payload"))
        return

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )

    try:
        await rate_user.execute(
            RateUserRequest(rater_id=user.id, rated_id=rated_user_id, score=score)
        )
    except CannotRateSelf:
        await callback.answer(_("Can't rate yourself"), show_alert=True)
        return
    except InvalidScore:
        await callback.answer(_("Bad score"))
        return

    await callback.answer(_("Rated {score}/10 ✓").format(score=score))
    await _notify_rated_user(bot, user_repo, rated_user_id, score)

    if isinstance(callback.message, Message):
        await _strip_keyboard(callback.message)
        # Read the updated summary — same UoW committed it on `rate_user.execute`.
        score_resp = await get_profile_score.execute(rated_user_id)
        if score_resp is not None:
            await callback.message.answer(
                ngettext(
                    "📊 Their average: {avg}/10 (from {count} rating)",
                    "📊 Their average: {avg}/10 (from {count} ratings)",
                    score_resp.rating_count,
                ).format(
                    avg=f"{score_resp.average_score:.1f}",
                    count=score_resp.rating_count,
                )
            )
        await show_next_or_done(callback.message, user.id, get_next, state)


@router.callback_query(F.data.startswith("skip:"))
async def on_skip(
    callback: CallbackQuery,
    state: FSMContext,
    register_user: FromDishka[RegisterUserUseCase],
    skip_profile: FromDishka[SkipProfileUseCase],
    get_next: FromDishka[GetNextProfileForRatingUseCase],
) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer()
        return
    try:
        skipped_owner_id = UUID(parts[1])
    except ValueError:
        await callback.answer()
        return

    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    await skip_profile.execute(viewer_id=user.id, skipped_owner_id=skipped_owner_id)
    await callback.answer(_("Skipped"))

    if isinstance(callback.message, Message):
        await _strip_keyboard(callback.message)
        await show_next_or_done(callback.message, user.id, get_next, state)

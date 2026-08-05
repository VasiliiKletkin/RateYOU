import html
from collections.abc import Awaitable, Callable
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from aiogram.utils.i18n import ngettext
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.rating.dto import IncomingRatingItem
from src.application.rating.get_profile_score import GetProfileScoreUseCase
from src.application.rating.list_incoming_ratings import ListIncomingRatingsUseCase
from src.domain.shared.exceptions import PremiumRequired
from src.presentation.bot.i18n import normalize_language

router = Router(name="my_rating")


async def _send_my_rating(
    send: Callable[[str], Awaitable[Message]],
    *,
    user_id: UUID,
    get_profile_score: GetProfileScoreUseCase,
    list_use_case: ListIncomingRatingsUseCase,
) -> None:
    """Own score first (free), then who gave it (premium).

    The score is the hook and the list is what it sells, so a free user
    gets a real answer plus a reason to subscribe rather than a bare
    paywall. Both halves read the same ratings — the summary via the
    `ProfileScoreSummary` projection, the list row by row.
    """
    score = await get_profile_score.execute(user_id)
    if score is None:
        await send(_("No one has rated you yet."))
        return

    lines = [
        ngettext(
            "🌟 Your rating: {avg}/10 (from {count} rating)",
            "🌟 Your rating: {avg}/10 (from {count} ratings)",
            score.rating_count,
        ).format(avg=f"{score.average_score:.1f}", count=score.rating_count),
        "",
    ]

    try:
        response = await list_use_case.execute(user_id)
    except PremiumRequired:
        lines.append(_("🔒 This is a premium feature.\nUse /premium to subscribe."))
        await send("\n".join(lines))
        return

    if not response.items:
        # Summary says rated, list says empty — only reachable if the
        # projection drifted from the rows. Send the score alone.
        await send(lines[0])
        return

    lines.append(_("🌟 Latest people who rated you:"))
    lines.append("")
    for item in response.items:
        when = item.rated_at.strftime("%d.%m %H:%M")
        lines.append(f"⭐ {item.score}/10 — {_rater_contact(item)}, {when}")
    await send("\n".join(lines))


def _rater_contact(item: IncomingRatingItem) -> str:
    """Renders the rater as a tappable contact so the viewer can message them.

    Identified by User data only (no Profile lookup — raters aren't required
    to have one): the public t.me handle when present; accounts without a
    username (a large share on Telegram) fall back to a `tg://user?id=`
    mention with a localized placeholder, which resolves because the rater
    has already used this bot.

    The bot sends with parse_mode=HTML, so the handle is escaped before
    being embedded in the markup.
    """
    if item.rater_username:
        handle = html.escape(item.rater_username)
        return f'<a href="https://t.me/{handle}">@{handle}</a>'
    anonymous = html.escape(_("Anonymous"))
    if item.rater_telegram_id is not None:
        return f'<a href="tg://user?id={item.rater_telegram_id}">{anonymous}</a>'
    return anonymous


# `my_ratings` stays registered alongside the new name: the command was
# renamed after launch and the old one lives on in client history and
# autocomplete. Only `my_rating` is advertised in the command menu.
@router.message(Command("my_rating", "my_ratings"))
async def cmd_my_rating(
    message: Message,
    register_user: FromDishka[RegisterUserUseCase],
    get_profile_score: FromDishka[GetProfileScoreUseCase],
    list_incoming_ratings: FromDishka[ListIncomingRatingsUseCase],
) -> None:
    if message.from_user is None:
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=message.from_user.id,
            language=normalize_language(message.from_user.language_code),
        )
    )
    await _send_my_rating(
        message.answer,
        user_id=user.id,
        get_profile_score=get_profile_score,
        list_use_case=list_incoming_ratings,
    )


# Callback data deliberately NOT renamed with the command: keyboards already
# delivered to users keep sending the old payload forever.
@router.callback_query(F.data == "show_my_ratings")
async def on_show_my_rating(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
    get_profile_score: FromDishka[GetProfileScoreUseCase],
    list_incoming_ratings: FromDishka[ListIncomingRatingsUseCase],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    user = await register_user.execute(
        RegisterUserRequest(
            telegram_id=callback.from_user.id,
            language=normalize_language(callback.from_user.language_code),
        )
    )
    await callback.answer()
    await _send_my_rating(
        callback.message.answer,
        user_id=user.id,
        get_profile_score=get_profile_score,
        list_use_case=list_incoming_ratings,
    )

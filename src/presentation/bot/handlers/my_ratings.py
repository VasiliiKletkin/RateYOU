from collections.abc import Awaitable, Callable
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.application.rating.list_incoming_ratings import ListIncomingRatingsUseCase
from src.domain.shared.exceptions import PremiumRequired
from src.presentation.bot.i18n import normalize_language

router = Router(name="my_ratings")


async def _send_my_ratings(
    send: Callable[[str], Awaitable[Message]],
    *,
    user_id: UUID,
    list_use_case: ListIncomingRatingsUseCase,
) -> None:
    try:
        response = await list_use_case.execute(user_id)
    except PremiumRequired:
        await send(_("🔒 This is a premium feature.\nUse /premium to subscribe."))
        return

    if not response.items:
        await send(_("No one has rated you yet."))
        return

    lines = [_("🌟 Latest people who rated you:"), ""]
    for item in response.items:
        name = item.rater_name or _("Anonymous")
        when = item.rated_at.strftime("%d.%m %H:%M")
        lines.append(f"⭐ {item.score}/10 — {name}, {when}")
    await send("\n".join(lines))


@router.message(Command("my_ratings"))
async def cmd_my_ratings(
    message: Message,
    register_user: FromDishka[RegisterUserUseCase],
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
    await _send_my_ratings(
        message.answer,
        user_id=user.id,
        list_use_case=list_incoming_ratings,
    )


@router.callback_query(F.data == "show_my_ratings")
async def on_show_my_ratings(
    callback: CallbackQuery,
    register_user: FromDishka[RegisterUserUseCase],
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
    await _send_my_ratings(
        callback.message.answer,
        user_id=user.id,
        list_use_case=list_incoming_ratings,
    )

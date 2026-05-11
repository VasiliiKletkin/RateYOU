from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from dishka import AsyncContainer

from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import TelegramId


class BanCheckMiddleware(BaseMiddleware):
    """Short-circuits handlers if the Telegram user is banned.

    Reads the dishka request-scope container from `data["dishka_container"]`
    (populated by `setup_dishka(..., auto_inject=True)`) and resolves
    `IUserRepository` from it. Refused interactions get a soft reply or
    callback toast; no exception propagates.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return await handler(event, data)

        container: AsyncContainer | None = data.get("dishka_container")
        if container is None:
            return await handler(event, data)

        user_repo = await container.get(IUserRepository)
        user = await user_repo.get_by_telegram_id(TelegramId(tg_user.id))

        if user is not None and user.is_banned:
            if isinstance(event, Message):
                await event.answer("You are banned from this bot.")
            elif isinstance(event, CallbackQuery):
                await event.answer("You are banned", show_alert=True)
            return None

        return await handler(event, data)

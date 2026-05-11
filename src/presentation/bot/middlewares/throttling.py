from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis


@dataclass
class ThrottlingMiddleware(BaseMiddleware):
    """Per-user rate limiter backed by Redis.

    Uses `SET key value EX ttl NX` — atomic set-if-not-exists with expiry.
    First action by a user creates the key, subsequent ones within `ttl`
    fail the SET and are silently dropped.

    Media-group messages (gallery uploads) are exempt: Telegram delivers
    each photo of a single gallery as a separate Message, often within
    50-200ms of each other. Throttling them would drop every photo past
    the first one even though it's logically a single user action.
    """

    redis: Redis
    ttl_seconds: int = 1

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None:
            return await handler(event, data)

        if isinstance(event, Message) and event.media_group_id is not None:
            return await handler(event, data)

        key = f"throttle:{tg_user.id}"
        was_set = await self.redis.set(name=key, value="1", ex=self.ttl_seconds, nx=True)
        if not was_set:
            return None

        return await handler(event, data)

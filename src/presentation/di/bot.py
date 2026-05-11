from collections.abc import AsyncIterable

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.redis import RedisStorage
from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from src.infrastructure.config import Settings


class BotProvider(Provider):
    """Provides the aiogram Bot and the FSM storage. Single instance per process."""

    scope = Scope.APP

    @provide
    async def bot(self, settings: Settings) -> AsyncIterable[Bot]:
        bot = Bot(
            token=settings.bot.token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            yield bot
        finally:
            await bot.session.close()

    @provide
    def storage(self, redis: Redis) -> BaseStorage:
        return RedisStorage(redis=redis)

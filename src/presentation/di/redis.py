from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from src.infrastructure.config import Settings


class RedisProvider(Provider):
    """Single Redis client for the whole process (FSM storage + future caches)."""

    scope = Scope.APP

    @provide
    async def redis(self, settings: Settings) -> AsyncIterable[Redis]:
        redis = Redis.from_url(settings.redis.dsn)
        try:
            yield redis
        finally:
            await redis.aclose()

from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from src.domain.discovery.skip_registry import ISkipRegistry
from src.infrastructure.config import Settings
from src.infrastructure.discovery.redis_skip_registry import RedisSkipRegistry


class DiscoveryProvider(Provider):
    """Wires Discovery-specific infrastructure that isn't tied to a DB session."""

    scope = Scope.APP

    @provide
    def skip_registry(self, redis: Redis, settings: Settings) -> ISkipRegistry:
        return RedisSkipRegistry(
            redis=redis,
            ttl_seconds=settings.redis.skip_ttl_seconds,
        )

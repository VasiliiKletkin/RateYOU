from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from src.domain.discovery.skip_registry import ISkipRegistry
from src.infrastructure.discovery.redis_skip_registry import RedisSkipRegistry


class DiscoveryProvider(Provider):
    """Wires Discovery-specific infrastructure that isn't tied to a DB session."""

    scope = Scope.APP

    @provide
    def skip_registry(self, redis: Redis) -> ISkipRegistry:
        return RedisSkipRegistry(redis=redis)

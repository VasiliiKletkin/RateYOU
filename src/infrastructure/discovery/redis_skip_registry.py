from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from src.domain.shared.identifiers import UserId


@dataclass
class RedisSkipRegistry:
    """Stores skipped owner IDs in a Redis SET keyed by viewer.

    TTL applies to the set as a whole; any new `record_skip` resets it.
    Trade-off vs per-member TTL: simpler, but a continuous stream of skips
    keeps earlier entries alive. Good enough for MVP.
    """

    redis: Redis
    ttl_seconds: int = 3600  # 1 hour

    async def record_skip(
        self,
        viewer_id: UserId,
        skipped_owner_id: UserId,
    ) -> None:
        key = self._key(viewer_id)
        # redis-py's stubs declare sync|async Union returns on the async client;
        # mypy can't see the awaitable on sadd/smembers. expire works fine.
        await self.redis.sadd(key, str(skipped_owner_id.value))  # type: ignore[misc]
        await self.redis.expire(key, self.ttl_seconds)

    async def get_skipped(self, viewer_id: UserId) -> list[UserId]:
        members = await self.redis.smembers(self._key(viewer_id))  # type: ignore[misc]
        return [UserId(UUID(self._as_str(m))) for m in members]

    @staticmethod
    def _key(viewer_id: UserId) -> str:
        return f"skipped:{viewer_id.value}"

    @staticmethod
    def _as_str(member: bytes | str) -> str:
        return member.decode() if isinstance(member, bytes) else member

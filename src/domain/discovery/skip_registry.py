from typing import Protocol

from src.domain.shared.identifiers import UserId


class ISkipRegistry(Protocol):
    """Records which profile owners a viewer has skipped without rating.

    Entries are TTL'd — a skipped profile resurfaces in the feed after the
    cooldown expires, so the user gets a fresh chance to rate it later.
    Implemented by infrastructure/discovery/RedisSkipRegistry.
    """

    async def record_skip(
        self,
        viewer_id: UserId,
        skipped_owner_id: UserId,
    ) -> None: ...

    async def get_skipped(self, viewer_id: UserId) -> list[UserId]: ...

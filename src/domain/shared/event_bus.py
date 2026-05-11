from typing import Protocol

from src.domain.shared.events import DomainEvent


class IEventBus(Protocol):
    """Synchronous in-process dispatcher.

    Handlers run inside the calling use case's UoW — their failures roll the
    whole operation back. Switch to an outbox-backed bus when async or
    cross-process delivery is needed.
    """

    async def publish(self, event: DomainEvent) -> None: ...

    async def publish_all(self, events: list[DomainEvent]) -> None: ...

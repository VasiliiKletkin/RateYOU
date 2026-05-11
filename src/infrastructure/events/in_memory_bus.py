from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from src.domain.shared.events import DomainEvent

# `...` keeps mypy happy: handler signatures take a specific event subclass
# (contravariant w.r.t. DomainEvent), which would otherwise fail typing.
EventHandler = Callable[..., Awaitable[Any]]


@dataclass
class InMemoryEventBus:
    """Registry + dispatcher of handlers per event type.

    Constructed at REQUEST scope so each handler can hold REQUEST-scope
    dependencies (e.g. repositories on the same AsyncSession). All dispatch
    happens before the calling use case's `uow.commit()`, so handler writes
    join the same transaction.
    """

    _handlers: dict[type, list[EventHandler]] = field(default_factory=lambda: defaultdict(list))

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            await handler(event)

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

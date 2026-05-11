from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base for all domain events.

    Events are recorded on aggregates as state mutates and published by the
    use case after the aggregate is persisted. Subclasses are dataclasses
    with `kw_only=True` so the inherited `event_id` / `occurred_at` fields
    don't force ordering on subclass fields.
    """

    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)

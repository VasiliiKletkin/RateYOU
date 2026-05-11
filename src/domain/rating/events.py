from dataclasses import dataclass
from uuid import UUID

from src.domain.shared.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class RatingGiven(DomainEvent):
    """A user rated another user (newly or by changing their score)."""

    rater_id: UUID
    rated_id: UUID
    score: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RatingWithdrawn(DomainEvent):
    rater_id: UUID
    rated_id: UUID

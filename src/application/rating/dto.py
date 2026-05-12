from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RateUserRequest:
    rater_id: UUID
    rated_id: UUID
    score: int


@dataclass(frozen=True, slots=True)
class RatingResponse:
    id: UUID
    rater_id: UUID
    rated_id: UUID
    score: int


@dataclass(frozen=True, slots=True)
class ProfileScoreResponse:
    rated_id: UUID
    average_score: float
    rating_count: int


@dataclass(frozen=True, slots=True)
class IncomingRatingItem:
    rater_name: str | None
    score: int
    rated_at: datetime


@dataclass(frozen=True, slots=True)
class IncomingRatingsResponse:
    items: tuple[IncomingRatingItem, ...]

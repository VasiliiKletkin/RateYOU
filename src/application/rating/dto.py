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
    score: int
    rated_at: datetime
    # Contact handles for the rater. `rater_username` is None when the rater
    # has no Telegram handle — the presentation layer then falls back to a
    # `tg://user?id=` mention built from `rater_telegram_id`.
    rater_username: str | None = None
    rater_telegram_id: int | None = None


@dataclass(frozen=True, slots=True)
class IncomingRatingsResponse:
    items: tuple[IncomingRatingItem, ...]

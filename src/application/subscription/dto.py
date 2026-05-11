from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActivatePremiumRequest:
    owner_id: UUID
    tier: str  # "bronze" | "silver" | "gold"


@dataclass(frozen=True, slots=True)
class PremiumResponse:
    owner_id: UUID
    tier: str
    expires_at: datetime
    days_remaining: int
    min_rating_threshold: float


@dataclass(frozen=True, slots=True)
class TierInfoResponse:
    tier: str
    display_name: str
    stars_price: int
    duration_days: int
    min_rating_threshold: float

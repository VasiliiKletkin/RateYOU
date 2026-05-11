from dataclasses import dataclass
from datetime import datetime

from src.domain.shared.identifiers import UserId


@dataclass
class ProfileScoreSummary:
    """Read model: aggregated ratings stats for one rated user.

    Not an aggregate root — it is derived from all `Rating` rows where
    `rated_id == this user`. Recomputed and upserted whenever any rating
    for this user changes. Stored separately so Discovery can filter by
    average rating without aggregating on the hot path.
    """

    rated_id: UserId
    average_score: float
    rating_count: int
    updated_at: datetime

from dataclasses import dataclass

from src.domain.rating.events import RatingGiven, RatingWithdrawn
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.repositories import (
    IProfileScoreSummaryRepository,
    IRatingRepository,
)
from src.domain.shared.identifiers import UserId


@dataclass
class OnRatingGiven:
    """Refreshes the rated user's ProfileScoreSummary when a rating appears."""

    rating_repo: IRatingRepository
    summary_repo: IProfileScoreSummaryRepository

    async def handle(self, event: RatingGiven) -> None:
        await _refresh_summary(
            UserId(event.rated_id),
            event.occurred_at,
            self.rating_repo,
            self.summary_repo,
        )


@dataclass
class OnRatingWithdrawn:
    """Refreshes the rated user's ProfileScoreSummary after a rating is removed."""

    rating_repo: IRatingRepository
    summary_repo: IProfileScoreSummaryRepository

    async def handle(self, event: RatingWithdrawn) -> None:
        await _refresh_summary(
            UserId(event.rated_id),
            event.occurred_at,
            self.rating_repo,
            self.summary_repo,
        )


async def _refresh_summary(
    rated_id: UserId,
    now: object,  # datetime — typed as object since import would be circular noise
    rating_repo: IRatingRepository,
    summary_repo: IProfileScoreSummaryRepository,
) -> None:
    avg, count = await rating_repo.compute_stats_for(rated_id)
    from datetime import datetime  # local to keep top imports tidy

    occurred_at = now if isinstance(now, datetime) else datetime.now()
    await summary_repo.upsert(
        ProfileScoreSummary(
            rated_id=rated_id,
            average_score=avg,
            rating_count=count,
            updated_at=occurred_at,
        )
    )

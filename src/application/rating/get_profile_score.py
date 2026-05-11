from dataclasses import dataclass
from uuid import UUID

from src.application.rating.dto import ProfileScoreResponse
from src.domain.rating.repositories import IProfileScoreSummaryRepository
from src.domain.shared.identifiers import UserId


@dataclass
class GetProfileScoreUseCase:
    """Returns aggregated stats for a rated user, or None if never rated."""

    summary_repo: IProfileScoreSummaryRepository

    async def execute(self, rated_id: UUID) -> ProfileScoreResponse | None:
        summary = await self.summary_repo.get(UserId(rated_id))
        if summary is None or summary.rating_count == 0:
            return None
        return ProfileScoreResponse(
            rated_id=summary.rated_id.value,
            average_score=summary.average_score,
            rating_count=summary.rating_count,
        )

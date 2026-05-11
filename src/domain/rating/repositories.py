from typing import Protocol

from src.domain.rating.entities import Rating
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.value_objects import RatingId
from src.domain.shared.identifiers import UserId


class IRatingRepository(Protocol):
    async def add(self, rating: Rating) -> None: ...

    async def get_by_id(self, rating_id: RatingId) -> Rating | None: ...

    async def get_by_rater_and_rated(
        self,
        rater_id: UserId,
        rated_id: UserId,
    ) -> Rating | None: ...

    async def update(self, rating: Rating) -> None: ...

    async def delete(self, rating: Rating) -> None: ...

    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        """Returns (average_score, rating_count). avg=0.0, count=0 if no ratings."""
        ...


class IProfileScoreSummaryRepository(Protocol):
    async def upsert(self, summary: ProfileScoreSummary) -> None: ...

    async def get(self, rated_id: UserId) -> ProfileScoreSummary | None: ...

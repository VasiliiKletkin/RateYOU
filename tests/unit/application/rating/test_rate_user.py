from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from src.application.rating.dto import RateUserRequest
from src.application.rating.handlers import OnRatingGiven
from src.application.rating.rate_user import RateUserUseCase
from src.domain.rating.entities import Rating
from src.domain.rating.events import RatingGiven
from src.domain.rating.exceptions import CannotRateSelf
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.services import RatingFulfillmentService
from src.domain.rating.value_objects import RatingId
from src.domain.shared.identifiers import UserId
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


@dataclass
class FakeRatingRepository:
    ratings: dict[UUID, Rating] = field(default_factory=dict)

    async def add(self, rating: Rating) -> None:
        self.ratings[rating.id.value] = rating

    async def get_by_id(self, rating_id: RatingId) -> Rating | None:
        return self.ratings.get(rating_id.value)

    async def get_by_rater_and_rated(
        self,
        rater_id: UserId,
        rated_id: UserId,
    ) -> Rating | None:
        for r in self.ratings.values():
            if r.rater_id == rater_id and r.rated_id == rated_id:
                return r
        return None

    async def update(self, rating: Rating) -> None:
        self.ratings[rating.id.value] = rating

    async def delete(self, rating: Rating) -> None:
        self.ratings.pop(rating.id.value, None)

    async def compute_stats_for(self, rated_id: UserId) -> tuple[float, int]:
        scores = [r.score.value for r in self.ratings.values() if r.rated_id == rated_id]
        if not scores:
            return 0.0, 0
        return sum(scores) / len(scores), len(scores)


@dataclass
class FakeSummaryRepository:
    summaries: dict[UUID, ProfileScoreSummary] = field(default_factory=dict)

    async def upsert(self, summary: ProfileScoreSummary) -> None:
        self.summaries[summary.rated_id.value] = summary

    async def get(self, rated_id: UserId) -> ProfileScoreSummary | None:
        return self.summaries.get(rated_id.value)


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_use_case(
    ratings: FakeRatingRepository,
    summaries: FakeSummaryRepository,
    uow: FakeUoW,
) -> RateUserUseCase:
    service = RatingFulfillmentService(rating_repo=ratings)
    handler = OnRatingGiven(rating_repo=ratings, summary_repo=summaries)
    bus = InMemoryEventBus()
    bus.subscribe(RatingGiven, handler.handle)
    return RateUserUseCase(fulfillment_service=service, event_bus=bus, uow=uow)


async def test_first_rating_creates_and_updates_summary() -> None:
    ratings = FakeRatingRepository()
    summaries = FakeSummaryRepository()
    uow = FakeUoW()
    use_case = _make_use_case(ratings, summaries, uow)
    rater, rated = uuid4(), uuid4()

    response = await use_case.execute(
        RateUserRequest(rater_id=rater, rated_id=rated, score=7)
    )

    assert response.score == 7
    assert len(ratings.ratings) == 1
    summary = summaries.summaries[rated]
    assert summary.average_score == 7.0
    assert summary.rating_count == 1
    assert uow.committed is True


async def test_second_rater_changes_average() -> None:
    ratings = FakeRatingRepository()
    summaries = FakeSummaryRepository()
    uow = FakeUoW()
    use_case = _make_use_case(ratings, summaries, uow)
    rater_a, rater_b, rated = uuid4(), uuid4(), uuid4()

    await use_case.execute(RateUserRequest(rater_id=rater_a, rated_id=rated, score=6))
    await use_case.execute(RateUserRequest(rater_id=rater_b, rated_id=rated, score=10))

    summary = summaries.summaries[rated]
    assert summary.average_score == 8.0
    assert summary.rating_count == 2


async def test_re_rating_replaces_score() -> None:
    ratings = FakeRatingRepository()
    summaries = FakeSummaryRepository()
    uow = FakeUoW()
    use_case = _make_use_case(ratings, summaries, uow)
    rater, rated = uuid4(), uuid4()

    first = await use_case.execute(
        RateUserRequest(rater_id=rater, rated_id=rated, score=3)
    )
    second = await use_case.execute(
        RateUserRequest(rater_id=rater, rated_id=rated, score=9)
    )

    assert first.id == second.id
    assert second.score == 9
    assert len(ratings.ratings) == 1
    summary = summaries.summaries[rated]
    assert summary.average_score == 9.0
    assert summary.rating_count == 1


async def test_cannot_rate_self() -> None:
    ratings = FakeRatingRepository()
    summaries = FakeSummaryRepository()
    uow = FakeUoW()
    use_case = _make_use_case(ratings, summaries, uow)
    same = uuid4()

    with pytest.raises(CannotRateSelf):
        await use_case.execute(
            RateUserRequest(rater_id=same, rated_id=same, score=10)
        )

    assert uow.committed is False

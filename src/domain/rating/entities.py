from dataclasses import dataclass, field
from datetime import datetime

from src.domain.rating.events import RatingGiven, RatingWithdrawn
from src.domain.rating.exceptions import CannotRateSelf
from src.domain.rating.value_objects import RatingId, Score
from src.domain.shared.events import DomainEvent
from src.domain.shared.identifiers import UserId


@dataclass
class Rating:
    """Aggregate root: one rater's rating of one rated user.

    Invariant: rater_id != rated_id. One (rater_id, rated_id) pair has at most
    one Rating (enforced via UNIQUE constraint in DB + repository check).
    Re-rating the same user replaces the previous score via change_score().

    Records `RatingGiven` on create/update and `RatingWithdrawn` on delete —
    use case publishes them via the event bus after the repo write.
    """

    id: RatingId
    rater_id: UserId
    rated_id: UserId
    score: Score
    created_at: datetime
    updated_at: datetime
    _events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    @classmethod
    def give(
        cls,
        rater_id: UserId,
        rated_id: UserId,
        score: Score,
        now: datetime,
    ) -> "Rating":
        if rater_id == rated_id:
            raise CannotRateSelf(f"User {rater_id.value} cannot rate themselves")
        rating = cls(
            id=RatingId.new(),
            rater_id=rater_id,
            rated_id=rated_id,
            score=score,
            created_at=now,
            updated_at=now,
        )
        rating._events.append(
            RatingGiven(
                rater_id=rater_id.value,
                rated_id=rated_id.value,
                score=score.value,
                occurred_at=now,
            )
        )
        return rating

    def change_score(self, score: Score, now: datetime) -> None:
        self.score = score
        self.updated_at = now
        self._events.append(
            RatingGiven(
                rater_id=self.rater_id.value,
                rated_id=self.rated_id.value,
                score=score.value,
                occurred_at=now,
            )
        )

    def withdraw(self, now: datetime) -> None:
        self._events.append(
            RatingWithdrawn(
                rater_id=self.rater_id.value,
                rated_id=self.rated_id.value,
                occurred_at=now,
            )
        )

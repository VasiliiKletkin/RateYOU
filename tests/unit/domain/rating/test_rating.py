from datetime import UTC, datetime, timedelta

import pytest

from src.domain.rating.entities import Rating
from src.domain.rating.exceptions import CannotRateSelf
from src.domain.rating.value_objects import Score
from src.domain.shared.identifiers import UserId


def test_give_creates_rating_with_timestamps() -> None:
    now = datetime.now(UTC)
    rater, rated = UserId.new(), UserId.new()

    rating = Rating.give(rater, rated, Score(7), now)

    assert rating.rater_id == rater
    assert rating.rated_id == rated
    assert rating.score == Score(7)
    assert rating.created_at == now
    assert rating.updated_at == now


def test_give_with_self_raises() -> None:
    rater = UserId.new()
    with pytest.raises(CannotRateSelf):
        Rating.give(rater, rater, Score(5), datetime.now(UTC))


def test_change_score_updates_score_and_timestamp() -> None:
    now = datetime.now(UTC)
    later = now + timedelta(minutes=5)
    rating = Rating.give(UserId.new(), UserId.new(), Score(5), now)

    rating.change_score(Score(9), now=later)

    assert rating.score == Score(9)
    assert rating.updated_at == later
    assert rating.created_at == now  # unchanged

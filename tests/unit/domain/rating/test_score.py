import pytest

from src.domain.rating.exceptions import InvalidScore
from src.domain.rating.value_objects import Score


def test_accepts_zero() -> None:
    assert Score(0).value == 0


def test_accepts_ten() -> None:
    assert Score(10).value == 10


def test_accepts_middle() -> None:
    assert Score(7).value == 7


def test_rejects_negative() -> None:
    with pytest.raises(InvalidScore):
        Score(-1)


def test_rejects_above_max() -> None:
    with pytest.raises(InvalidScore):
        Score(11)

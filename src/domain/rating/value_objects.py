from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID, uuid4

from src.domain.rating.exceptions import InvalidScore


@dataclass(frozen=True, slots=True)
class RatingId:
    value: UUID

    @classmethod
    def new(cls) -> "RatingId":
        return cls(uuid4())


@dataclass(frozen=True, slots=True)
class Score:
    """0 means worst, 10 means best. Integer (discrete rating buttons in the bot)."""

    value: int
    MIN: ClassVar[int] = 0
    MAX: ClassVar[int] = 10

    def __post_init__(self) -> None:
        if not (self.MIN <= self.value <= self.MAX):
            raise InvalidScore(
                f"Score must be between {self.MIN} and {self.MAX}, got {self.value}"
            )

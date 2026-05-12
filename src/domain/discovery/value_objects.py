from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from src.domain.discovery.exceptions import InvalidMinRating


class GenderPreference(StrEnum):
    """Who the viewer wants to see in their feed.

    `ANY` disables the gender filter; `MALE` / `FEMALE` restrict candidates
    to profiles of that gender. Lives in Discovery because it's a search
    preference, not a description of the user themselves.
    """

    MALE = "male"
    FEMALE = "female"
    ANY = "any"


@dataclass(frozen=True, slots=True)
class MinRating:
    """Minimum average rating a candidate must have to appear in the feed.

    `0` means no filter — profiles with no ratings pass through. Anything
    above `0` filters out profiles whose `average_score` is lower (and, via
    the INNER JOIN on summaries, profiles with no ratings yet).
    """

    value: int
    MIN: ClassVar[int] = 0
    MAX: ClassVar[int] = 10

    def __post_init__(self) -> None:
        if not (self.MIN <= self.value <= self.MAX):
            raise InvalidMinRating(
                f"Min rating must be in [{self.MIN}, {self.MAX}], got {self.value}"
            )

    @property
    def is_active(self) -> bool:
        return self.value > 0

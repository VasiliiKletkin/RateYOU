from dataclasses import dataclass
from datetime import datetime

from src.domain.discovery.value_objects import GenderPreference, MinRating
from src.domain.profile.value_objects import Location
from src.domain.shared.identifiers import UserId


@dataclass
class SearchPreferences:
    """Per-user feed preferences. 1:1 with User.

    Lives in Discovery because it shapes the candidate query (not what the
    user shows to others — that's the Profile aggregate). Created with safe
    defaults on first /create or first /settings access, then mutated via
    `change_*` methods.

    `location` is the origin the feed sorts candidates around by distance.
    It is what lets a user browse *without* a profile of their own — the
    feed no longer borrows the viewer's own `Profile.location`. `None` means
    the viewer hasn't set a search area yet, so the feed can't run.
    """

    user_id: UserId
    gender_preference: GenderPreference
    min_rating: MinRating
    location: Location | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def default(cls, user_id: UserId, now: datetime) -> "SearchPreferences":
        return cls(
            user_id=user_id,
            gender_preference=GenderPreference.ANY,
            min_rating=MinRating(0),
            location=None,
            created_at=now,
            updated_at=now,
        )

    def change_gender_preference(self, preference: GenderPreference, now: datetime) -> None:
        self.gender_preference = preference
        self.updated_at = now

    def change_min_rating(self, min_rating: MinRating, now: datetime) -> None:
        self.min_rating = min_rating
        self.updated_at = now

    def change_location(self, location: Location, now: datetime) -> None:
        self.location = location
        self.updated_at = now

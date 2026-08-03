from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class NextProfileResponse:
    """The next profile to show a viewer for rating.

    Owns its shape independently from Profile context's ProfileResponse —
    Discovery adds derived fields (distance from viewer) that Profile
    wouldn't expose on its own.
    """

    profile_id: UUID
    owner_id: UUID
    name: str
    age: int
    gender: str
    bio: str
    photo_file_ids: tuple[str, ...]  # 1..6, ordered
    distance_meters: int  # geodesic distance from viewer's location


@dataclass(frozen=True, slots=True)
class BroadcastRecipient:
    """One person to nudge, with everything the sender needs.

    `language` is a plain locale code rather than the Identity enum so the
    Discovery contract doesn't drag another context's value object along.

    No count of new profiles: the message deliberately doesn't quote one, and
    deciding *whether* someone has anything new stays inside the use case.
    """

    user_id: UUID
    telegram_id: int
    language: str


@dataclass(frozen=True, slots=True)
class NewProfilesBroadcast:
    """Who should hear about profiles added since the last run. Empty = stay quiet."""

    recipients: tuple[BroadcastRecipient, ...]


@dataclass(frozen=True, slots=True)
class SearchPreferencesResponse:
    user_id: UUID
    gender_preference: str  # "male" | "female" | "any"
    min_rating: int  # 0..10; 0 = no filter
    has_location: bool  # False = no search area set yet, feed can't run

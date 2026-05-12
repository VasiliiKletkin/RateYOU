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
class SearchPreferencesResponse:
    user_id: UUID
    gender_preference: str  # "male" | "female" | "any"
    min_rating: int  # 0..10; 0 = no filter

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateProfileRequest:
    owner_id: UUID
    name: str
    age: int
    gender: str  # "male" | "female"
    bio: str
    photo_file_ids: tuple[str, ...]  # 1..6
    location: tuple[float, float]  # (lat, lon) — required


@dataclass(frozen=True, slots=True)
class EditProfileRequest:
    profile_id: UUID
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    bio: str | None = None
    # None = don't change. Non-None replaces the whole set (1..6).
    photo_file_ids: tuple[str, ...] | None = None
    location: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class ProfileResponse:
    id: UUID
    owner_id: UUID
    name: str
    age: int
    gender: str
    bio: str
    photo_file_ids: tuple[str, ...]
    location: tuple[float, float]
    is_visible: bool

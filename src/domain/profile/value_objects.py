from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar
from uuid import UUID, uuid4

from src.domain.profile.exceptions import (
    InvalidAge,
    InvalidLocation,
    InvalidName,
    InvalidPhoto,
    InvalidPhotos,
)


@dataclass(frozen=True, slots=True)
class ProfileId:
    value: UUID

    @classmethod
    def new(cls) -> "ProfileId":
        return cls(uuid4())


@dataclass(frozen=True, slots=True)
class Name:
    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise InvalidName("Name cannot be empty")
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True, slots=True)
class Age:
    value: int
    MIN: ClassVar[int] = 18
    MAX: ClassVar[int] = 100

    def __post_init__(self) -> None:
        if not (self.MIN <= self.value <= self.MAX):
            raise InvalidAge(f"Age must be between {self.MIN} and {self.MAX}, got {self.value}")


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


@dataclass(frozen=True, slots=True)
class Bio:
    value: str


@dataclass(frozen=True, slots=True)
class Location:
    """Geographic point in WGS84. `lat` is north-south, `lon` is east-west.

    Stored in PostGIS as geography(POINT, 4326) — the mapper converts to
    a WKT/WKB element. Order matters: PostGIS POINT is (lon, lat).
    """

    lat: float
    lon: float
    LAT_MIN: ClassVar[float] = -90.0
    LAT_MAX: ClassVar[float] = 90.0
    LON_MIN: ClassVar[float] = -180.0
    LON_MAX: ClassVar[float] = 180.0

    def __post_init__(self) -> None:
        if not (self.LAT_MIN <= self.lat <= self.LAT_MAX):
            raise InvalidLocation(
                f"Latitude must be in [{self.LAT_MIN}, {self.LAT_MAX}], got {self.lat}"
            )
        if not (self.LON_MIN <= self.lon <= self.LON_MAX):
            raise InvalidLocation(
                f"Longitude must be in [{self.LON_MIN}, {self.LON_MAX}], got {self.lon}"
            )


@dataclass(frozen=True, slots=True)
class PhotoFileId:
    """Telegram file_id for the profile photo.

    Stored as-is from Telegram; resolved to an actual URL via Bot API
    when displaying. Not validated as a URL — Telegram file_ids are opaque.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise InvalidPhoto("Photo file_id cannot be empty")
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True, slots=True)
class Photos:
    """Ordered collection of 1..6 profile photos.

    Min = 1 because /create requires the user to send at least one photo.
    Max = 6 matches Telegram's media_group limit with comfortable headroom
    (Telegram allows up to 10 but most clients render 6 cleanly).
    """

    items: tuple[PhotoFileId, ...]
    MIN_COUNT: ClassVar[int] = 1
    MAX_COUNT: ClassVar[int] = 6

    def __post_init__(self) -> None:
        if len(self.items) < self.MIN_COUNT:
            raise InvalidPhotos(
                f"At least {self.MIN_COUNT} photo required, got {len(self.items)}"
            )
        if len(self.items) > self.MAX_COUNT:
            raise InvalidPhotos(
                f"Max {self.MAX_COUNT} photos, got {len(self.items)}"
            )

    @classmethod
    def from_strings(cls, file_ids: list[str]) -> "Photos":
        return cls(items=tuple(PhotoFileId(fid) for fid in file_ids))

    def to_strings(self) -> list[str]:
        return [p.value for p in self.items]

    @property
    def first(self) -> PhotoFileId:
        return self.items[0]

    def __len__(self) -> int:
        return len(self.items)

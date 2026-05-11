from dataclasses import dataclass
from datetime import datetime

from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    Photos,
    ProfileId,
)
from src.domain.shared.identifiers import UserId


@dataclass
class Profile:
    """Aggregate root of the Profile context.

    Represents what a user shows to others. Owned by a User (Identity context)
    via owner_id. Photos are an ordered collection (1..6) handled as a single
    Photos VO — the individual PhotoFileId is not an entity in this iteration.
    Location is required — profiles without geo aren't accepted.
    """

    id: ProfileId
    owner_id: UserId
    name: Name
    age: Age
    gender: Gender
    bio: Bio
    photos: Photos
    location: Location
    created_at: datetime
    updated_at: datetime
    is_visible: bool = True

    @classmethod
    def create(
        cls,
        owner_id: UserId,
        name: Name,
        age: Age,
        gender: Gender,
        bio: Bio,
        photos: Photos,
        location: Location,
        now: datetime,
    ) -> "Profile":
        return cls(
            id=ProfileId.new(),
            owner_id=owner_id,
            name=name,
            age=age,
            gender=gender,
            bio=bio,
            photos=photos,
            location=location,
            created_at=now,
            updated_at=now,
        )

    def update_basics(
        self,
        name: Name | None,
        age: Age | None,
        gender: Gender | None,
        now: datetime,
    ) -> None:
        if name is not None:
            self.name = name
        if age is not None:
            self.age = age
        if gender is not None:
            self.gender = gender
        self.updated_at = now

    def update_bio(self, bio: Bio, now: datetime) -> None:
        self.bio = bio
        self.updated_at = now

    def update_photos(self, photos: Photos, now: datetime) -> None:
        self.photos = photos
        self.updated_at = now

    def update_location(self, location: Location, now: datetime) -> None:
        self.location = location
        self.updated_at = now

    def hide(self, now: datetime) -> None:
        self.is_visible = False
        self.updated_at = now

    def show(self, now: datetime) -> None:
        self.is_visible = True
        self.updated_at = now

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.profile.dto import EditProfileRequest, ProfileResponse
from src.domain.profile.exceptions import ProfileNotFound
from src.domain.profile.repositories import IProfileRepository
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    Photos,
    ProfileId,
)
from src.domain.shared.uow import UnitOfWork


@dataclass
class EditProfileUseCase:
    """Applies any subset of profile fields. Missing fields stay unchanged."""

    profile_repo: IProfileRepository
    uow: UnitOfWork

    async def execute(self, request: EditProfileRequest) -> ProfileResponse:
        profile = await self.profile_repo.get_by_id(ProfileId(request.profile_id))
        if profile is None:
            raise ProfileNotFound(f"Profile {request.profile_id} not found")

        now = datetime.now(UTC)

        profile.update_basics(
            name=Name(request.name) if request.name is not None else None,
            age=Age(request.age) if request.age is not None else None,
            gender=Gender(request.gender) if request.gender is not None else None,
            now=now,
        )

        if request.bio is not None:
            profile.update_bio(Bio(request.bio), now)

        if request.photo_file_ids is not None:
            profile.update_photos(Photos.from_strings(list(request.photo_file_ids)), now)

        if request.location is not None:
            profile.update_location(Location(lat=request.location[0], lon=request.location[1]), now)

        await self.profile_repo.update(profile)
        await self.uow.commit()

        return ProfileResponse(
            id=profile.id.value,
            owner_id=profile.owner_id.value,
            name=profile.name.value,
            age=profile.age.value,
            gender=profile.gender.value,
            bio=profile.bio.value,
            photo_file_ids=tuple(profile.photos.to_strings()),
            location=(profile.location.lat, profile.location.lon),
            is_visible=profile.is_visible,
        )

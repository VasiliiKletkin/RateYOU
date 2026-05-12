from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.profile.dto import CreateProfileRequest, ProfileResponse
from src.domain.profile.entities import Profile
from src.domain.profile.exceptions import ProfileAlreadyExists
from src.domain.profile.repositories import IProfileRepository
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    Photos,
)
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class CreateProfileUseCase:
    """Creates a new profile for an already-registered user.

    The caller (handler) must have ensured the user exists in the Identity
    context. One profile per owner is enforced via exists_for_owner check
    and a UNIQUE constraint at the DB level.
    """

    profile_repo: IProfileRepository
    uow: UnitOfWork

    async def execute(self, request: CreateProfileRequest) -> ProfileResponse:
        owner_id = UserId(request.owner_id)

        if await self.profile_repo.exists_for_owner(owner_id):
            raise ProfileAlreadyExists(f"User {owner_id.value} already has a profile")

        profile = Profile.create(
            owner_id=owner_id,
            name=Name(request.name),
            age=Age(request.age),
            gender=Gender(request.gender),
            bio=Bio(request.bio),
            photos=Photos.from_strings(list(request.photo_file_ids)),
            location=Location(lat=request.location[0], lon=request.location[1]),
            now=datetime.now(UTC),
        )
        await self.profile_repo.add(profile)
        await self.uow.commit()
        return _to_response(profile)


def _to_response(profile: Profile) -> ProfileResponse:
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

from dataclasses import dataclass
from uuid import UUID

from src.application.profile.dto import ProfileResponse
from src.domain.profile.repositories import IProfileRepository
from src.domain.shared.identifiers import UserId


@dataclass
class GetMyProfileUseCase:
    """Returns the profile owned by user, or None if not yet created."""

    profile_repo: IProfileRepository

    async def execute(self, owner_id: UUID) -> ProfileResponse | None:
        profile = await self.profile_repo.get_by_owner_id(UserId(owner_id))
        if profile is None:
            return None
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

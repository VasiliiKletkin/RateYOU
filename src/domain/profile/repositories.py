from typing import Protocol

from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import ProfileId
from src.domain.shared.identifiers import UserId


class IProfileRepository(Protocol):
    """Persistence interface for the Profile aggregate.

    Implemented by infrastructure/db/repositories/profile.ProfileRepository.
    """

    async def add(self, profile: Profile) -> None: ...

    async def get_by_id(self, profile_id: ProfileId) -> Profile | None: ...

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None: ...

    async def exists_for_owner(self, owner_id: UserId) -> bool: ...

    async def update(self, profile: Profile) -> None: ...

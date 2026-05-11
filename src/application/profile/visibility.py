from dataclasses import dataclass
from datetime import UTC, datetime

from src.domain.profile.exceptions import ProfileNotFound
from src.domain.profile.repositories import IProfileRepository
from src.domain.profile.value_objects import ProfileId
from src.domain.shared.uow import UnitOfWork


@dataclass
class HideProfileUseCase:
    profile_repo: IProfileRepository
    uow: UnitOfWork

    async def execute(self, profile_id: ProfileId) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if profile is None:
            raise ProfileNotFound(f"Profile {profile_id.value} not found")
        profile.hide(now=datetime.now(UTC))
        await self.profile_repo.update(profile)
        await self.uow.commit()


@dataclass
class ShowProfileUseCase:
    profile_repo: IProfileRepository
    uow: UnitOfWork

    async def execute(self, profile_id: ProfileId) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if profile is None:
            raise ProfileNotFound(f"Profile {profile_id.value} not found")
        profile.show(now=datetime.now(UTC))
        await self.profile_repo.update(profile)
        await self.uow.commit()

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import ProfileId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.profile import (
    _location_to_wkt,
    orm_to_profile,
    profile_to_orm,
)
from src.infrastructure.db.models.profile import ProfileORM, ProfilePhotoORM


@dataclass
class ProfileRepository:
    session: AsyncSession

    async def add(self, profile: Profile) -> None:
        self.session.add(profile_to_orm(profile))
        await self.session.flush()

    async def get_by_id(self, profile_id: ProfileId) -> Profile | None:
        result = await self.session.execute(
            select(ProfileORM)
            .where(ProfileORM.id == profile_id.value)
            .options(selectinload(ProfileORM.photos))
        )
        orm = result.scalar_one_or_none()
        return orm_to_profile(orm) if orm is not None else None

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None:
        result = await self.session.execute(
            select(ProfileORM)
            .where(ProfileORM.owner_id == owner_id.value)
            .options(selectinload(ProfileORM.photos))
        )
        orm = result.scalar_one_or_none()
        return orm_to_profile(orm) if orm is not None else None

    async def exists_for_owner(self, owner_id: UserId) -> bool:
        result = await self.session.execute(
            select(ProfileORM.id).where(ProfileORM.owner_id == owner_id.value).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def update(self, profile: Profile) -> None:
        existing = await self.session.get(
            ProfileORM,
            profile.id.value,
            options=[selectinload(ProfileORM.photos)],
        )
        if existing is None:
            raise ValueError(f"Profile {profile.id.value} not found for update")
        existing.name = profile.name.value
        existing.age = profile.age.value
        existing.gender = profile.gender.value
        existing.bio = profile.bio.value
        existing.is_visible = profile.is_visible
        # SQLAlchemy accepts WKTElement for a Geography(WKBElement) column —
        # the type hierarchy is just narrower than the runtime behaviour.
        existing.location = _location_to_wkt(profile.location)  # type: ignore[assignment]
        existing.updated_at = profile.updated_at
        self._reconcile_photos(existing, profile)
        await self.session.flush()

    def _reconcile_photos(self, existing: ProfileORM, profile: Profile) -> None:
        """Replace-all strategy: drop everything, recreate with fresh positions.

        With ≤6 photos and an indexed FK, deleting+inserting beats diffing —
        simpler code, identical I/O. `cascade="all, delete-orphan"` on the
        relationship turns the .clear() into proper DELETE statements when
        we flush.
        """
        existing.photos.clear()
        existing.photos.extend(
            ProfilePhotoORM(
                id=uuid4(),
                profile_id=profile.id.value,
                file_id=photo.value,
                position=idx,
            )
            for idx, photo in enumerate(profile.photos.items)
        )

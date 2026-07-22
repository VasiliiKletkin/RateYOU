from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Name,
    PhotoFileId,
    Photos,
    ProfileId,
)
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.geo import location_to_wkt, wkb_to_location
from src.infrastructure.db.models.profile import ProfileORM, ProfilePhotoORM


@dataclass
class ProfileRepository:
    session: AsyncSession

    async def add(self, profile: Profile) -> None:
        orm = ProfileORM(
            id=profile.id.value,
            owner_id=profile.owner_id.value,
            name=profile.name.value,
            age=profile.age.value,
            gender=profile.gender,
            bio=profile.bio.value,
            is_visible=profile.is_visible,
            location=location_to_wkt(profile.location),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        orm.photos = [
            ProfilePhotoORM(
                id=uuid4(),
                profile_id=profile.id.value,
                file_id=photo.value,
                position=idx,
            )
            for idx, photo in enumerate(profile.photos.items)
        ]
        self.session.add(orm)
        await self.session.flush()

    async def get_by_id(self, profile_id: ProfileId) -> Profile | None:
        result = await self.session.execute(
            select(ProfileORM)
            .where(ProfileORM.id == profile_id.value)
            .options(selectinload(ProfileORM.photos))
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return Profile(
            id=ProfileId(orm.id),
            owner_id=UserId(orm.owner_id),
            name=Name(orm.name),
            age=Age(orm.age),
            gender=orm.gender,
            bio=Bio(orm.bio),
            # Defensive sort — the relationship already orders by position,
            # but a stale session might not. Cheap insurance.
            photos=Photos(
                items=tuple(
                    PhotoFileId(p.file_id) for p in sorted(orm.photos, key=lambda p: p.position)
                )
            ),
            location=wkb_to_location(orm.location),
            is_visible=orm.is_visible,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None:
        result = await self.session.execute(
            select(ProfileORM)
            .where(ProfileORM.owner_id == owner_id.value)
            .options(selectinload(ProfileORM.photos))
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return Profile(
            id=ProfileId(orm.id),
            owner_id=UserId(orm.owner_id),
            name=Name(orm.name),
            age=Age(orm.age),
            gender=orm.gender,
            bio=Bio(orm.bio),
            photos=Photos(
                items=tuple(
                    PhotoFileId(p.file_id) for p in sorted(orm.photos, key=lambda p: p.position)
                )
            ),
            location=wkb_to_location(orm.location),
            is_visible=orm.is_visible,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def exists_for_owner(self, owner_id: UserId) -> bool:
        result = await self.session.execute(
            select(ProfileORM.id).where(ProfileORM.owner_id == owner_id.value).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_owner_ids_created_after(self, since: datetime) -> list[UserId]:
        """Owners of profiles that appeared after `since` — the "what's new" set.

        Hidden profiles are excluded: they can't show up in anyone's feed, so
        announcing them would promise something the feed won't deliver.
        """
        result = await self.session.execute(
            select(ProfileORM.owner_id)
            .where(ProfileORM.created_at > since)
            .where(ProfileORM.is_visible.is_(True))
        )
        return [UserId(owner_id) for owner_id in result.scalars()]

    async def list_visible_owner_ids(self) -> list[UserId]:
        """Everyone with a live profile — i.e. everyone who can use the feed."""
        result = await self.session.execute(
            select(ProfileORM.owner_id).where(ProfileORM.is_visible.is_(True))
        )
        return [UserId(owner_id) for owner_id in result.scalars()]

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
        existing.gender = profile.gender
        existing.bio = profile.bio.value
        existing.is_visible = profile.is_visible
        # SQLAlchemy accepts WKTElement for a Geography(WKBElement) column —
        # the type hierarchy is just narrower than the runtime behaviour.
        existing.location = location_to_wkt(profile.location)  # type: ignore[assignment]
        existing.updated_at = profile.updated_at
        await self._reconcile_photos(existing, profile)
        await self.session.flush()

    async def _reconcile_photos(self, existing: ProfileORM, profile: Profile) -> None:
        """Replace-all strategy: drop everything, recreate with fresh positions.

        With ≤6 photos and an indexed FK, deleting+inserting beats diffing —
        simpler code, identical I/O. `cascade="all, delete-orphan"` on the
        relationship turns the .clear() into proper DELETE statements when
        we flush. We flush BETWEEN the clear and the extend so the old rows
        leave the DB before new rows reuse their (profile_id, position).
        """
        existing.photos.clear()
        await self.session.flush()
        existing.photos.extend(
            ProfilePhotoORM(
                id=uuid4(),
                profile_id=profile.id.value,
                file_id=photo.value,
                position=idx,
            )
            for idx, photo in enumerate(profile.photos.items)
        )

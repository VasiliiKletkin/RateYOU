from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.discovery.entities import SearchPreferences
from src.domain.discovery.value_objects import MinRating
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.discovery import SearchPreferencesORM


@dataclass
class SearchPreferencesRepository:
    session: AsyncSession

    async def get_for(self, user_id: UserId) -> SearchPreferences | None:
        result = await self.session.execute(
            select(SearchPreferencesORM).where(SearchPreferencesORM.user_id == user_id.value)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return SearchPreferences(
            user_id=UserId(orm.user_id),
            gender_preference=orm.gender_preference,
            min_rating=MinRating(orm.min_rating),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def add(self, prefs: SearchPreferences) -> None:
        self.session.add(
            SearchPreferencesORM(
                user_id=prefs.user_id.value,
                gender_preference=prefs.gender_preference,
                min_rating=prefs.min_rating.value,
                created_at=prefs.created_at,
                updated_at=prefs.updated_at,
            )
        )
        await self.session.flush()

    async def update(self, prefs: SearchPreferences) -> None:
        existing = await self.session.get(SearchPreferencesORM, prefs.user_id.value)
        if existing is None:
            raise ValueError(f"SearchPreferences for {prefs.user_id.value} not found for update")
        existing.gender_preference = prefs.gender_preference
        existing.min_rating = prefs.min_rating.value
        existing.updated_at = prefs.updated_at
        await self.session.flush()

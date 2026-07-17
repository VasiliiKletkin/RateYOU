from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.discovery.entities import SearchPreferences
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.discovery import (
    orm_to_search_preferences,
    search_preferences_to_orm,
)
from src.infrastructure.db.models.discovery import SearchPreferencesORM


@dataclass
class SearchPreferencesRepository:
    session: AsyncSession

    async def get_for(self, user_id: UserId) -> SearchPreferences | None:
        result = await self.session.execute(
            select(SearchPreferencesORM).where(SearchPreferencesORM.user_id == user_id.value)
        )
        orm = result.scalar_one_or_none()
        return orm_to_search_preferences(orm) if orm is not None else None

    async def add(self, prefs: SearchPreferences) -> None:
        self.session.add(search_preferences_to_orm(prefs))
        await self.session.flush()

    async def update(self, prefs: SearchPreferences) -> None:
        existing = await self.session.get(SearchPreferencesORM, prefs.user_id.value)
        if existing is None:
            raise ValueError(f"SearchPreferences for {prefs.user_id.value} not found for update")
        existing.gender_preference = prefs.gender_preference
        existing.min_rating = prefs.min_rating.value
        existing.updated_at = prefs.updated_at
        await self.session.flush()

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.discovery.dto import SearchPreferencesResponse
from src.domain.discovery.entities import SearchPreferences
from src.domain.discovery.repositories import ISearchPreferencesRepository
from src.domain.discovery.value_objects import GenderPreference, MinRating
from src.domain.profile.value_objects import Location
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class GetSearchPreferencesUseCase:
    """Returns prefs for the user, materialising defaults on first access.

    Auto-creating on read keeps callers (/settings, feed) simple — they
    never have to handle a missing row.
    """

    prefs_repo: ISearchPreferencesRepository
    uow: UnitOfWork

    async def execute(self, user_id: UUID) -> SearchPreferencesResponse:
        uid = UserId(user_id)
        prefs = await self.prefs_repo.get_for(uid)
        if prefs is None:
            prefs = SearchPreferences.default(uid, datetime.now(UTC))
            await self.prefs_repo.add(prefs)
            await self.uow.commit()
        return SearchPreferencesResponse(
            user_id=prefs.user_id.value,
            gender_preference=prefs.gender_preference.value,
            min_rating=prefs.min_rating.value,
            has_location=prefs.location is not None,
        )


@dataclass
class UpdateGenderPreferenceUseCase:
    """Sets the viewer's gender preference, creating the row if missing."""

    prefs_repo: ISearchPreferencesRepository
    uow: UnitOfWork

    async def execute(self, user_id: UUID, preference: str) -> SearchPreferencesResponse:
        uid = UserId(user_id)
        now = datetime.now(UTC)
        pref = GenderPreference(preference)
        prefs = await self.prefs_repo.get_for(uid)
        if prefs is None:
            prefs = SearchPreferences.default(uid, now)
            prefs.change_gender_preference(pref, now)
            await self.prefs_repo.add(prefs)
        else:
            prefs.change_gender_preference(pref, now)
            await self.prefs_repo.update(prefs)
        await self.uow.commit()
        return SearchPreferencesResponse(
            user_id=prefs.user_id.value,
            gender_preference=prefs.gender_preference.value,
            min_rating=prefs.min_rating.value,
            has_location=prefs.location is not None,
        )


@dataclass
class UpdateMinRatingUseCase:
    """Sets the viewer's min-rating filter, creating the row if missing."""

    prefs_repo: ISearchPreferencesRepository
    uow: UnitOfWork

    async def execute(self, user_id: UUID, min_rating: int) -> SearchPreferencesResponse:
        uid = UserId(user_id)
        now = datetime.now(UTC)
        value = MinRating(min_rating)
        prefs = await self.prefs_repo.get_for(uid)
        if prefs is None:
            prefs = SearchPreferences.default(uid, now)
            prefs.change_min_rating(value, now)
            await self.prefs_repo.add(prefs)
        else:
            prefs.change_min_rating(value, now)
            await self.prefs_repo.update(prefs)
        await self.uow.commit()
        return SearchPreferencesResponse(
            user_id=prefs.user_id.value,
            gender_preference=prefs.gender_preference.value,
            min_rating=prefs.min_rating.value,
            has_location=prefs.location is not None,
        )


@dataclass
class UpdateSearchLocationUseCase:
    """Sets the viewer's search origin, creating the prefs row if missing.

    This is what unblocks the feed for a user without a profile: the origin
    the feed sorts around no longer comes from `Profile.location`.
    """

    prefs_repo: ISearchPreferencesRepository
    uow: UnitOfWork

    async def execute(
        self, user_id: UUID, latitude: float, longitude: float
    ) -> SearchPreferencesResponse:
        uid = UserId(user_id)
        now = datetime.now(UTC)
        location = Location(lat=latitude, lon=longitude)
        prefs = await self.prefs_repo.get_for(uid)
        if prefs is None:
            prefs = SearchPreferences.default(uid, now)
            prefs.change_location(location, now)
            await self.prefs_repo.add(prefs)
        else:
            prefs.change_location(location, now)
            await self.prefs_repo.update(prefs)
        await self.uow.commit()
        return SearchPreferencesResponse(
            user_id=prefs.user_id.value,
            gender_preference=prefs.gender_preference.value,
            min_rating=prefs.min_rating.value,
            has_location=prefs.location is not None,
        )

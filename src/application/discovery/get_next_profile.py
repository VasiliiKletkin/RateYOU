from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.discovery.dto import NextProfileResponse
from src.domain.discovery.repositories import (
    IDiscoveryRepository,
    ISearchPreferencesRepository,
)
from src.domain.discovery.skip_registry import ISkipRegistry
from src.domain.discovery.specifications import (
    ProfileAverageRatingAtLeast,
    ProfileHasGender,
    ProfileOwnerNotIn,
    default_feed_spec,
)
from src.domain.discovery.value_objects import GenderPreference
from src.domain.profile.repositories import IProfileRepository
from src.domain.profile.value_objects import Gender
from src.domain.shared.identifiers import UserId
from src.domain.shared.specifications import Specification
from src.domain.subscription.entities import SubscriptionStatus
from src.domain.subscription.repositories import ISubscriptionRepository


@dataclass
class GetNextProfileForRatingUseCase:
    """Composes a feed Specification per request and asks the repo to match it.

    Layers of filtering, all expressed as `Specification`s:
      - `default_feed_spec`: visible + not own + not already rated
      - `ProfileHasGender`: viewer's gender preference (if not ANY)
      - `ProfileAverageRatingAtLeast`: viewer's min-rating filter — only
        honoured for currently-premium users (stored value lingers after
        premium expires, ignored until they renew)
      - `ProfileOwnerNotIn`: recently skipped owners (Redis cooldown)

    Ordering: if the viewer has shared their location (read from their own
    profile), candidates are sorted by distance ASC with NULLS LAST so
    nearer profiles come first and location-less ones still appear.
    """

    discovery_repo: IDiscoveryRepository
    profile_repo: IProfileRepository
    prefs_repo: ISearchPreferencesRepository
    subscription_repo: ISubscriptionRepository
    skip_registry: ISkipRegistry

    async def execute(self, viewer_id: UUID) -> NextProfileResponse | None:
        viewer = UserId(viewer_id)

        viewer_profile = await self.profile_repo.get_by_owner_id(viewer)
        if viewer_profile is None:
            # No profile = no /feed access. Handler-level guard already
            # blocks this, but bail defensively.
            return None

        spec: Specification = default_feed_spec(viewer)

        prefs = await self.prefs_repo.get_for(viewer)
        if prefs is not None and prefs.gender_preference != GenderPreference.ANY:
            # ANY disables the filter; the other two enums map 1:1 to Gender
            # so the lookup is safe.
            spec = spec & ProfileHasGender(Gender(prefs.gender_preference.value))

        if prefs is not None and prefs.min_rating.is_active and await self._is_premium(viewer):
            spec = spec & ProfileAverageRatingAtLeast(float(prefs.min_rating.value))

        skipped = await self.skip_registry.get_skipped(viewer)
        if skipped:
            spec = spec & ProfileOwnerNotIn(user_ids=tuple(skipped))

        match = await self.discovery_repo.find_next(spec, viewer_profile.location)
        if match is None:
            return None
        profile = match.profile
        return NextProfileResponse(
            profile_id=profile.id.value,
            owner_id=profile.owner_id.value,
            name=profile.name.value,
            age=profile.age.value,
            gender=profile.gender.value,
            bio=profile.bio.value,
            photo_file_ids=tuple(profile.photos.to_strings()),
            distance_meters=match.distance_meters,
        )

    async def _is_premium(self, viewer: UserId) -> bool:
        grants = await self.subscription_repo.list_for(viewer)
        status = SubscriptionStatus.from_grants(grants, datetime.now(UTC))
        return status.is_active

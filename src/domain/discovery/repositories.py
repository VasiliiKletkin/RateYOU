from dataclasses import dataclass
from typing import Protocol

from src.domain.discovery.entities import SearchPreferences
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import Location
from src.domain.shared.identifiers import UserId
from src.domain.shared.specifications import Specification


@dataclass(frozen=True, slots=True)
class DiscoveryMatch:
    """Profile + the geodesic distance (meters) from the viewer to it."""

    profile: Profile
    distance_meters: int


class IDiscoveryRepository(Protocol):
    """Picks the next candidate profile that matches the given specification.

    The caller composes a `Specification` describing what counts as a
    candidate (visible, not viewer's own, premium threshold, not skipped…).
    The infrastructure side compiles it to SQL — the domain stays free of
    query DSLs. Candidates are ordered by distance ASC from the viewer.
    """

    async def find_next(
        self,
        spec: Specification,
        viewer_location: Location,
    ) -> DiscoveryMatch | None: ...


class ISearchPreferencesRepository(Protocol):
    """CRUD for the `SearchPreferences` aggregate (1:1 with User)."""

    async def get_for(self, user_id: UserId) -> SearchPreferences | None: ...
    async def add(self, prefs: SearchPreferences) -> None: ...
    async def update(self, prefs: SearchPreferences) -> None: ...

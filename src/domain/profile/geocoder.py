from dataclasses import dataclass
from typing import Protocol

from src.domain.profile.value_objects import Location


@dataclass(frozen=True, slots=True)
class GeocodeCandidate:
    """One possible place a free-text query resolved to.

    Free text is ambiguous — "Rostov" matches both Rostov-on-Don and Rostov
    Veliky — so geocoding yields a list and the caller lets the user choose.
    `label` is already human-readable and localised, ready to show as-is.
    """

    label: str
    location: Location


class IGeocoder(Protocol):
    """Turns a place name into candidate coordinates.

    Implemented by infrastructure/geocoding. Returns an empty list when
    nothing matched — that is a normal outcome (typos, made-up names), not
    an error, and callers must handle it.

    Raises `GeocodingUnavailable` when the upstream service failed, so the
    caller can tell "no such place" apart from "try again later".
    """

    async def geocode(
        self,
        query: str,
        *,
        language: str,
        limit: int = 5,
    ) -> list[GeocodeCandidate]: ...

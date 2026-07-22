import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from src.domain.profile.exceptions import GeocodingUnavailable, InvalidLocation
from src.domain.profile.geocoder import GeocodeCandidate
from src.domain.profile.value_objects import Location

log = logging.getLogger(__name__)

# Telegram renders long button captions badly, so labels get clipped.
_MAX_LABEL_LENGTH = 60


@dataclass
class NominatimGeocoder:
    """Geocodes place names against a Nominatim (OpenStreetMap) instance.

    Deliberately restricted to settlements: the profile feed only sorts by
    distance, so city-level precision is enough, and asking strangers for a
    street address would be a privacy problem. `featureType=settlement`
    keeps house numbers and streets out of the results.

    The public instance allows ~1 request/second, which is why this is meant
    to sit behind `CachedGeocoder` — city queries repeat heavily.
    """

    base_url: str
    user_agent: str
    timeout_seconds: float = 5.0

    async def geocode(
        self,
        query: str,
        *,
        language: str,
        limit: int = 5,
    ) -> list[GeocodeCandidate]:
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": str(limit),
            "addressdetails": "1",
            "featureType": "settlement",
            "accept-language": language,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(
                    self.base_url,
                    params=params,
                    headers={"User-Agent": self.user_agent},
                ) as response,
            ):
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.warning(f"Geocoding request failed for {query!r}: {exc}")
            raise GeocodingUnavailable(str(exc)) from exc

        if not isinstance(payload, list):
            raise GeocodingUnavailable(f"Unexpected payload type: {type(payload).__name__}")

        candidates = [self._to_candidate(item) for item in payload]
        return [c for c in candidates if c is not None]

    def _to_candidate(self, item: Any) -> GeocodeCandidate | None:
        """Maps one raw result, dropping anything malformed rather than failing.

        A single unusable entry shouldn't lose the user the other matches.
        """
        if not isinstance(item, dict):
            return None
        try:
            location = Location(lat=float(item["lat"]), lon=float(item["lon"]))
        except (KeyError, TypeError, ValueError, InvalidLocation):
            return None
        return GeocodeCandidate(label=self._to_label(item), location=location)

    def _to_label(self, item: dict[str, Any]) -> str:
        """Builds "City, Region, Country" — `display_name` is far too verbose."""
        address = item.get("address") or {}
        region = address.get("state") or address.get("region") or address.get("county")
        parts = [
            item.get("name") or address.get("city") or item.get("display_name", ""),
            region,
            address.get("country"),
        ]
        label = ", ".join(str(p) for p in parts if p)
        if len(label) > _MAX_LABEL_LENGTH:
            label = label[: _MAX_LABEL_LENGTH - 1].rstrip() + "…"
        return label

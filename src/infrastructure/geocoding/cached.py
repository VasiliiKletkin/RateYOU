import json
import logging
from dataclasses import dataclass

from redis.asyncio import Redis

from src.domain.profile.geocoder import GeocodeCandidate, IGeocoder
from src.domain.profile.value_objects import Location

log = logging.getLogger(__name__)


@dataclass
class CachedGeocoder:
    """Redis cache in front of another geocoder.

    City names repeat across users far more than they differ, so this keeps
    almost all traffic off the upstream service — which matters because the
    public Nominatim instance allows only ~1 request/second.

    Failures (`GeocodingUnavailable`) are never cached: they propagate so the
    caller can say "try again later", and the next attempt hits upstream.
    """

    inner: IGeocoder
    redis: Redis
    ttl_seconds: int = 30 * 24 * 3600
    miss_ttl_seconds: int = 3600

    async def geocode(
        self,
        query: str,
        *,
        language: str,
        limit: int = 5,
    ) -> list[GeocodeCandidate]:
        key = self._key(query, language, limit)
        cached = await self.redis.get(key)
        if cached is not None:
            decoded = self._decode(cached)
            if decoded is not None:
                return decoded

        candidates = await self.inner.geocode(query, language=language, limit=limit)
        # Empty results are cached too — repeated typos shouldn't each cost an
        # upstream call — but only briefly, since coverage improves over time.
        await self.redis.set(
            key,
            self._encode(candidates),
            ex=self.ttl_seconds if candidates else self.miss_ttl_seconds,
        )
        return candidates

    def _key(self, query: str, language: str, limit: int) -> str:
        return f"geocode:{language}:{limit}:{' '.join(query.lower().split())}"

    def _encode(self, candidates: list[GeocodeCandidate]) -> str:
        return json.dumps(
            [{"label": c.label, "lat": c.location.lat, "lon": c.location.lon} for c in candidates]
        )

    def _decode(self, raw: bytes | str) -> list[GeocodeCandidate] | None:
        """Returns None on anything unreadable so the caller re-queries upstream."""
        try:
            items = json.loads(raw)
            return [
                GeocodeCandidate(
                    label=item["label"],
                    location=Location(lat=item["lat"], lon=item["lon"]),
                )
                for item in items
            ]
        except (ValueError, TypeError, KeyError) as exc:
            log.warning(f"Discarding unreadable geocode cache entry: {exc}")
            return None

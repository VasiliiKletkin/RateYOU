from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from src.domain.profile.geocoder import IGeocoder
from src.infrastructure.config import Settings
from src.infrastructure.geocoding import CachedGeocoder, NominatimGeocoder


class GeocodingProvider(Provider):
    """Wires place-name lookup used by the manual city entry in /create."""

    scope = Scope.APP

    @provide
    def geocoder(self, redis: Redis, settings: Settings) -> IGeocoder:
        # Always wrapped in the cache: the public Nominatim instance allows
        # roughly one request per second across all of our users.
        return CachedGeocoder(
            inner=NominatimGeocoder(
                base_url=settings.geocoding.base_url,
                user_agent=settings.geocoding.user_agent,
                timeout_seconds=settings.geocoding.timeout_seconds,
            ),
            redis=redis,
            ttl_seconds=settings.geocoding.cache_ttl_seconds,
            miss_ttl_seconds=settings.geocoding.cache_miss_ttl_seconds,
        )

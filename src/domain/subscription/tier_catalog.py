from collections.abc import Mapping
from dataclasses import dataclass

from src.domain.subscription.exceptions import InvalidTier
from src.domain.subscription.value_objects import Tier


@dataclass(frozen=True, slots=True)
class TierSpec:
    """Business rules of a premium tier.

    Static catalog defined in code — there is no `tiers` DB table. To change
    prices or thresholds, edit the catalog and ship a release.
    """

    tier: Tier
    display_name: str
    stars_price: int
    duration_days: int
    min_rating_threshold: float


TIER_CATALOG: Mapping[Tier, TierSpec] = {
    Tier.BRONZE: TierSpec(
        tier=Tier.BRONZE,
        display_name="Bronze",
        stars_price=100,
        duration_days=7,
        min_rating_threshold=6.0,
    ),
    Tier.SILVER: TierSpec(
        tier=Tier.SILVER,
        display_name="Silver",
        stars_price=300,
        duration_days=30,
        min_rating_threshold=7.0,
    ),
    Tier.GOLD: TierSpec(
        tier=Tier.GOLD,
        display_name="Gold",
        stars_price=1000,
        duration_days=30,
        min_rating_threshold=8.0,
    ),
}


def get_tier_spec(tier: Tier) -> TierSpec:
    try:
        return TIER_CATALOG[tier]
    except KeyError as exc:
        raise InvalidTier(f"Unknown tier: {tier}") from exc


def all_tier_specs() -> list[TierSpec]:
    return list(TIER_CATALOG.values())

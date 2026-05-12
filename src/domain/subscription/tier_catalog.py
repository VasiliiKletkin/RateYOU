from collections.abc import Mapping
from dataclasses import dataclass

from src.domain.subscription.exceptions import InvalidTier
from src.domain.subscription.value_objects import Tier


@dataclass(frozen=True, slots=True)
class TierSpec:
    """Business rules of a premium tier.

    Static catalog defined in code — there is no `tiers` DB table. To change
    prices or duration, edit the catalog and ship a release. The actual
    rating filter is no longer baked into tiers — premium users set it
    themselves via /settings, gated on having an active subscription.
    """

    tier: Tier
    display_name: str
    stars_price: int
    duration_days: int


TIER_CATALOG: Mapping[Tier, TierSpec] = {
    Tier.BRONZE: TierSpec(
        tier=Tier.BRONZE,
        display_name="Bronze",
        stars_price=100,
        duration_days=7,
    ),
    Tier.SILVER: TierSpec(
        tier=Tier.SILVER,
        display_name="Silver",
        stars_price=300,
        duration_days=30,
    ),
    Tier.GOLD: TierSpec(
        tier=Tier.GOLD,
        display_name="Gold",
        stars_price=1000,
        duration_days=30,
    ),
}


def get_tier_spec(tier: Tier) -> TierSpec:
    try:
        return TIER_CATALOG[tier]
    except KeyError as exc:
        raise InvalidTier(f"Unknown tier: {tier}") from exc


def all_tier_specs() -> list[TierSpec]:
    return list(TIER_CATALOG.values())

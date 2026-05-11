import pytest

from src.domain.subscription.exceptions import InvalidTier
from src.domain.subscription.tier_catalog import all_tier_specs, get_tier_spec
from src.domain.subscription.value_objects import Tier


def test_get_tier_spec_returns_each_tier() -> None:
    bronze = get_tier_spec(Tier.BRONZE)
    silver = get_tier_spec(Tier.SILVER)
    gold = get_tier_spec(Tier.GOLD)

    assert bronze.tier == Tier.BRONZE
    assert silver.tier == Tier.SILVER
    assert gold.tier == Tier.GOLD


def test_tier_prices_are_monotonic() -> None:
    bronze = get_tier_spec(Tier.BRONZE)
    silver = get_tier_spec(Tier.SILVER)
    gold = get_tier_spec(Tier.GOLD)

    assert bronze.stars_price < silver.stars_price < gold.stars_price


def test_tier_thresholds_are_monotonic() -> None:
    bronze = get_tier_spec(Tier.BRONZE)
    silver = get_tier_spec(Tier.SILVER)
    gold = get_tier_spec(Tier.GOLD)

    assert bronze.min_rating_threshold < silver.min_rating_threshold < gold.min_rating_threshold


def test_all_tier_specs_returns_all_three() -> None:
    specs = all_tier_specs()
    assert len(specs) == 3


def test_get_tier_spec_raises_for_invalid() -> None:
    with pytest.raises(InvalidTier):
        # Bypass the StrEnum by faking an unknown member via cast
        get_tier_spec("platinum")  # type: ignore[arg-type]

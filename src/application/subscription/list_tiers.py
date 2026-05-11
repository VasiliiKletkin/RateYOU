from dataclasses import dataclass

from src.application.subscription.dto import TierInfoResponse
from src.domain.subscription.tier_catalog import all_tier_specs


@dataclass
class ListTiersUseCase:
    """Returns all available tiers for display in the bot's buy menu.

    Pure read of the static catalog — no repository needed.
    """

    async def execute(self) -> list[TierInfoResponse]:
        return [
            TierInfoResponse(
                tier=spec.tier.value,
                display_name=spec.display_name,
                stars_price=spec.stars_price,
                duration_days=spec.duration_days,
                min_rating_threshold=spec.min_rating_threshold,
            )
            for spec in all_tier_specs()
        ]

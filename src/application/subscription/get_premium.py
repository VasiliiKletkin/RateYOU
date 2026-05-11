from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.subscription.dto import PremiumResponse
from src.domain.shared.identifiers import UserId
from src.domain.subscription.repositories import ISubscriptionRepository
from src.domain.subscription.tier_catalog import get_tier_spec


@dataclass
class GetMyPremiumUseCase:
    """Returns active premium state, or None if user has no/expired/revoked sub."""

    subscription_repo: ISubscriptionRepository

    async def execute(self, owner_id: UUID) -> PremiumResponse | None:
        sub = await self.subscription_repo.get_for(UserId(owner_id))
        if sub is None:
            return None
        now = datetime.now(UTC)
        if not sub.is_active_at(now):
            return None
        spec = get_tier_spec(sub.tier)
        return PremiumResponse(
            owner_id=sub.owner_id.value,
            tier=sub.tier.value,
            expires_at=sub.expires_at,
            days_remaining=max(0, (sub.expires_at - now).days),
            min_rating_threshold=spec.min_rating_threshold,
        )

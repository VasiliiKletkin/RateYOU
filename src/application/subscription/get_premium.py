from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.subscription.dto import PremiumResponse
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionStatus
from src.domain.subscription.repositories import ISubscriptionRepository


@dataclass
class GetMyPremiumUseCase:
    """Returns active premium state, or None if user has no/expired/revoked grants.

    Projects the user's grant ledger into a `SubscriptionStatus` and packages
    it as a DTO. The active tier follows priority rules (GOLD > SILVER >
    BRONZE > BONUS); `expires_at` is the latest active grant's expiry.
    """

    subscription_repo: ISubscriptionRepository

    async def execute(self, owner_id: UUID) -> PremiumResponse | None:
        now = datetime.now(UTC)
        grants = await self.subscription_repo.list_for(UserId(owner_id))
        status = SubscriptionStatus.from_grants(grants, now)
        if not status.is_active:
            return None
        assert status.tier is not None and status.expires_at is not None
        return PremiumResponse(
            owner_id=owner_id,
            tier=status.tier.value,
            expires_at=status.expires_at,
            days_remaining=max(0, (status.expires_at - now).days),
        )

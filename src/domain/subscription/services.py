from dataclasses import dataclass
from datetime import datetime

from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.repositories import ISubscriptionRepository
from src.domain.subscription.tier_catalog import get_tier_spec
from src.domain.subscription.value_objects import Tier


@dataclass
class SubscriptionActivationService:
    """Activates a subscription for a given tier.

    Domain service: spans the lifecycle of the Subscription aggregate but does
    NOT commit. Callers (use cases) own the transaction boundary.

    Used by both `ActivatePremiumUseCase` (admin / direct activation) and
    `ConfirmPaymentUseCase` (fulfillment after a successful payment) — keeping
    the "create or renew_or_upgrade" logic in one place.
    """

    subscription_repo: ISubscriptionRepository

    async def activate(
        self,
        owner_id: UserId,
        tier: Tier,
        now: datetime,
    ) -> Subscription:
        spec = get_tier_spec(tier)
        existing = await self.subscription_repo.get_for(owner_id)
        if existing is None:
            sub = Subscription.activate(owner_id, tier, spec.duration_days, now)
            await self.subscription_repo.add(sub)
            return sub
        existing.renew_or_upgrade(tier, spec.duration_days, now)
        await self.subscription_repo.update(existing)
        return existing

    async def revoke(self, owner_id: UserId, now: datetime) -> None:
        sub = await self.subscription_repo.get_for(owner_id)
        if sub is None:
            return
        sub.revoke(now=now)
        await self.subscription_repo.update(sub)

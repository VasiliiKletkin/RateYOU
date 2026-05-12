from dataclasses import dataclass
from datetime import datetime

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.repositories import ISubscriptionRepository
from src.domain.subscription.tier_catalog import get_tier_spec
from src.domain.subscription.value_objects import Tier


@dataclass
class SubscriptionActivationService:
    """Orchestrates grant creation and revocation against the ledger.

    Domain service: composes Subscription repo operations to express the
    high-level "activate / refund / kill premium" intents. Does NOT commit.
    Callers (use cases / event handlers) own the transaction boundary.

    Policies:
      - A new PURCHASE revokes all of the owner's currently-active PURCHASE
        grants (the long-standing "remaining paid days are forfeited" rule),
        then creates a fresh grant. BONUS grants are NOT touched.
      - Refund revokes exactly the grant linked to the refunded transaction.
      - Admin "kill premium now" revokes every currently-active grant.
    """

    subscription_repo: ISubscriptionRepository

    async def activate_purchase(
        self,
        owner_id: UserId,
        tier: Tier,
        transaction_id: TransactionId | None,
        now: datetime,
    ) -> SubscriptionGrant:
        spec = get_tier_spec(tier)
        for active in await self.subscription_repo.list_active_purchases_for(
            owner_id, now
        ):
            active.revoke(now)
            await self.subscription_repo.update(active)
        grant = SubscriptionGrant.create_purchase(
            owner_id=owner_id,
            tier=tier,
            duration_days=spec.duration_days,
            transaction_id=transaction_id,
            now=now,
        )
        await self.subscription_repo.add(grant)
        return grant

    async def revoke_for_transaction(
        self,
        transaction_id: TransactionId,
        now: datetime,
    ) -> None:
        grant = await self.subscription_repo.find_by_transaction(transaction_id)
        if grant is None or grant.is_revoked:
            return
        grant.revoke(now)
        await self.subscription_repo.update(grant)

    async def revoke_all_active(
        self,
        owner_id: UserId,
        now: datetime,
    ) -> None:
        for grant in await self.subscription_repo.list_for(owner_id):
            if grant.is_active_at(now):
                grant.revoke(now)
                await self.subscription_repo.update(grant)

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.value_objects import (
    GrantId,
    GrantSource,
    Tier,
    tier_priority,
)


@dataclass
class SubscriptionGrant:
    """Aggregate root: a single grant of premium days from one source.

    Replaces the older single-row-per-user `Subscription`. Each purchase,
    bonus or admin grant is its own row — current premium state is derived
    by projecting the user's grants through `SubscriptionStatus.from_grants`.

    `transaction_id` links a PURCHASE grant back to the Payment context so
    refunds can revoke exactly that grant without touching bonuses.
    """

    id: GrantId
    owner_id: UserId
    tier: Tier
    source: GrantSource
    transaction_id: TransactionId | None
    starts_at: datetime
    expires_at: datetime
    is_revoked: bool
    created_at: datetime

    @classmethod
    def create_purchase(
        cls,
        owner_id: UserId,
        tier: Tier,
        duration_days: int,
        transaction_id: TransactionId | None,
        now: datetime,
    ) -> "SubscriptionGrant":
        return cls(
            id=GrantId.new(),
            owner_id=owner_id,
            tier=tier,
            source=GrantSource.PURCHASE,
            transaction_id=transaction_id,
            starts_at=now,
            expires_at=now + timedelta(days=duration_days),
            is_revoked=False,
            created_at=now,
        )

    @classmethod
    def create_bonus(
        cls,
        owner_id: UserId,
        duration_days: int,
        now: datetime,
    ) -> "SubscriptionGrant":
        return cls(
            id=GrantId.new(),
            owner_id=owner_id,
            tier=Tier.BONUS,
            source=GrantSource.BONUS,
            transaction_id=None,
            starts_at=now,
            expires_at=now + timedelta(days=duration_days),
            is_revoked=False,
            created_at=now,
        )

    def revoke(self, now: datetime) -> None:
        """Audit-friendly revoke: keeps the row, flips the flag, ends now."""
        self.is_revoked = True
        self.expires_at = now

    def is_active_at(self, when: datetime) -> bool:
        return not self.is_revoked and self.expires_at > when


@dataclass(frozen=True, slots=True)
class SubscriptionStatus:
    """Derived read model: the user's current premium state.

    Not persisted — projected from a list of grants by `from_grants`. The
    chosen `tier` is the highest-priority active grant (paid tiers shadow
    BONUS); `expires_at` is the latest active grant's expiry. If no grant
    is active, returns an inactive status with `tier=None`, `expires_at=None`.
    """

    is_active: bool
    tier: Tier | None
    expires_at: datetime | None

    @classmethod
    def inactive(cls) -> "SubscriptionStatus":
        return cls(is_active=False, tier=None, expires_at=None)

    @classmethod
    def from_grants(
        cls,
        grants: list[SubscriptionGrant],
        now: datetime,
    ) -> "SubscriptionStatus":
        active = [g for g in grants if g.is_active_at(now)]
        if not active:
            return cls.inactive()
        tier = max(active, key=lambda g: tier_priority(g.tier)).tier
        expires_at = max(g.expires_at for g in active)
        return cls(is_active=True, tier=tier, expires_at=expires_at)

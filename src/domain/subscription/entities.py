from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.shared.identifiers import UserId
from src.domain.subscription.value_objects import Tier


@dataclass
class Subscription:
    """Aggregate root: a user's current premium state.

    Identified by `owner_id` — there is at most one Subscription per user.
    Each purchase **replaces** the previous tier/period (remaining days of
    the old tier are forfeited; this is the policy choice).
    """

    owner_id: UserId
    tier: Tier
    expires_at: datetime
    is_revoked: bool
    updated_at: datetime

    @classmethod
    def activate(
        cls,
        owner_id: UserId,
        tier: Tier,
        duration_days: int,
        now: datetime,
    ) -> "Subscription":
        return cls(
            owner_id=owner_id,
            tier=tier,
            expires_at=now + timedelta(days=duration_days),
            is_revoked=False,
            updated_at=now,
        )

    def renew_or_upgrade(
        self,
        tier: Tier,
        duration_days: int,
        now: datetime,
    ) -> None:
        """Replaces the tier and resets the expiry to now + duration_days.

        Old remaining days are not preserved. Re-activates a revoked sub.
        """
        self.tier = tier
        self.expires_at = now + timedelta(days=duration_days)
        self.is_revoked = False
        self.updated_at = now

    def revoke(self, now: datetime) -> None:
        """Used by admin / refund flow. Premium ends immediately."""
        self.is_revoked = True
        self.expires_at = now
        self.updated_at = now

    def is_active_at(self, when: datetime) -> bool:
        return not self.is_revoked and self.expires_at > when

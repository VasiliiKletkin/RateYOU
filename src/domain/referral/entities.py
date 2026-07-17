from dataclasses import dataclass
from datetime import datetime

from src.domain.referral.exceptions import SelfReferral
from src.domain.referral.value_objects import ReferralId
from src.domain.shared.identifiers import UserId


@dataclass
class Referral:
    """Aggregate root: one referrer→referee invitation lifecycle.

    Single source of truth for who-invited-whom. The row is created the
    moment the referee clicks `/start <referrer_telegram_id>` and lives
    forever (no deletion). `rewarded_at` distinguishes the two states:

      - ``rewarded_at is None``  → pending. Referee hasn't created their
        profile yet, no bonus paid out.
      - ``rewarded_at is not None`` → both parties received their BONUS
        SubscriptionGrants.

    Invariants:
      - `referrer_id != referee_id` (enforced in `create_pending`)
      - At most one Referral per `referee_id` (DB-enforced UNIQUE)
      - `rewarded_at` is monotonic: once set, never cleared
    """

    id: ReferralId
    referrer_id: UserId
    referee_id: UserId
    created_at: datetime
    rewarded_at: datetime | None

    @classmethod
    def create_pending(
        cls,
        referrer_id: UserId,
        referee_id: UserId,
        now: datetime,
    ) -> "Referral":
        if referrer_id == referee_id:
            raise SelfReferral(f"User {referee_id.value} cannot refer themselves")
        return cls(
            id=ReferralId.new(),
            referrer_id=referrer_id,
            referee_id=referee_id,
            created_at=now,
            rewarded_at=None,
        )

    def mark_rewarded(self, now: datetime) -> None:
        """Sets the reward timestamp. Idempotent — repeated calls don't
        overwrite the original timestamp."""
        if self.rewarded_at is not None:
            return
        self.rewarded_at = now

    @property
    def is_rewarded(self) -> bool:
        return self.rewarded_at is not None

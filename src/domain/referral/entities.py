from dataclasses import dataclass
from datetime import datetime

from src.domain.referral.exceptions import (
    InvalidReferralStatusTransition,
    SelfReferral,
)
from src.domain.referral.value_objects import ReferralId, ReferralStatus
from src.domain.shared.identifiers import UserId


@dataclass
class Referral:
    """Aggregate root: tracks one referrer→referee invitation lifecycle.

    Invariants:
      - `referrer_id != referee_id` (enforced in `create_pending`)
      - At most one Referral per `referee_id` (DB-enforced UNIQUE)
      - State transitions are forward-only: PENDING → QUALIFIED → REWARDED

    `profile_created` and `first_rating_given` are independent partial-progress
    flags. The aggregate transitions to QUALIFIED only when both are set;
    callers (the service) then immediately drive QUALIFIED → REWARDED in the
    same UoW. The QUALIFIED state is therefore transient on disk.
    """

    id: ReferralId
    referrer_id: UserId
    referee_id: UserId
    status: ReferralStatus
    profile_created: bool
    first_rating_given: bool
    created_at: datetime
    qualified_at: datetime | None
    rewarded_at: datetime | None

    @classmethod
    def create_pending(
        cls,
        referrer_id: UserId,
        referee_id: UserId,
        now: datetime,
    ) -> "Referral":
        if referrer_id == referee_id:
            raise SelfReferral(
                f"User {referee_id.value} cannot refer themselves"
            )
        return cls(
            id=ReferralId.new(),
            referrer_id=referrer_id,
            referee_id=referee_id,
            status=ReferralStatus.PENDING,
            profile_created=False,
            first_rating_given=False,
            created_at=now,
            qualified_at=None,
            rewarded_at=None,
        )

    def mark_profile_created(self, now: datetime) -> bool:
        """Sets the profile flag. Returns True iff this call transitioned
        the aggregate into QUALIFIED."""
        if self.profile_created:
            return False
        self.profile_created = True
        return self._maybe_qualify(now)

    def mark_first_rating(self, now: datetime) -> bool:
        """Sets the first-rating flag. Returns True iff this call transitioned
        the aggregate into QUALIFIED."""
        if self.first_rating_given:
            return False
        self.first_rating_given = True
        return self._maybe_qualify(now)

    def _maybe_qualify(self, now: datetime) -> bool:
        if not (self.profile_created and self.first_rating_given):
            return False
        if self.status != ReferralStatus.PENDING:
            return False
        self.status = ReferralStatus.QUALIFIED
        self.qualified_at = now
        return True

    def mark_rewarded(self, now: datetime) -> None:
        if self.status == ReferralStatus.REWARDED:
            return  # idempotent retry
        if self.status != ReferralStatus.QUALIFIED:
            raise InvalidReferralStatusTransition(
                f"Cannot reward referral in status {self.status}"
            )
        self.status = ReferralStatus.REWARDED
        self.rewarded_at = now

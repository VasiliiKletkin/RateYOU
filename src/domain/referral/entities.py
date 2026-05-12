from dataclasses import dataclass
from datetime import datetime

from src.domain.referral.exceptions import SelfReferral
from src.domain.referral.value_objects import ReferralId
from src.domain.shared.identifiers import UserId


@dataclass
class Referral:
    """Aggregate root: an append-only record of a paid-out referral.

    A row exists iff the referee created their profile and both parties
    received their bonus grants. There is no PENDING state — invitations
    that never produce a profile are derived from the `users` table
    (rows with `referred_by_user_id` and no Referral entry).

    Invariants:
      - `referrer_id != referee_id` (enforced in `reward`)
      - At most one Referral per `referee_id` (DB-enforced UNIQUE)
      - Append-only: rows are never updated or revoked
    """

    id: ReferralId
    referrer_id: UserId
    referee_id: UserId
    created_at: datetime

    @classmethod
    def reward(
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
            created_at=now,
        )

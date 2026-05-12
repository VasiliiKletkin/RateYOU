from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ReferralId:
    value: UUID

    @classmethod
    def new(cls) -> "ReferralId":
        return cls(uuid4())


class ReferralStatus(StrEnum):
    """Lifecycle of a referral.

    PENDING: referee registered via deep link; either profile or first
        rating still missing.
    QUALIFIED: both conditions met. Transient state — the service
        immediately advances to REWARDED in the same UoW.
    REWARDED: bonus grants issued for referrer and referee.
    """

    PENDING = "pending"
    QUALIFIED = "qualified"
    REWARDED = "rewarded"

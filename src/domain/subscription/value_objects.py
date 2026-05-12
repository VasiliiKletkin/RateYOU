from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4


class Tier(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    BONUS = "bonus"


class GrantSource(StrEnum):
    PURCHASE = "purchase"
    BONUS = "bonus"


# Higher number = higher priority when projecting active grants into the
# user-facing SubscriptionStatus.tier. BONUS is intentionally the lowest so
# paid tiers always shadow gifted days in displays.
_TIER_PRIORITY: dict[Tier, int] = {
    Tier.BONUS: 0,
    Tier.BRONZE: 1,
    Tier.SILVER: 2,
    Tier.GOLD: 3,
}


def tier_priority(tier: Tier) -> int:
    return _TIER_PRIORITY[tier]


@dataclass(frozen=True, slots=True)
class GrantId:
    value: UUID

    @classmethod
    def new(cls) -> "GrantId":
        return cls(uuid4())

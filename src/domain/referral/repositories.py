from typing import Protocol

from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId


class IReferralRepository(Protocol):
    async def add(self, referral: Referral) -> None: ...

    async def get_by_referee(self, referee_id: UserId) -> Referral | None: ...

    async def update(self, referral: Referral) -> None: ...

    async def count_total_for_referrer(self, referrer_id: UserId) -> int:
        """All invitations (pending + rewarded). Drives the `Invitations`
        counter in /refer."""
        ...

    async def count_rewarded_for_referrer(self, referrer_id: UserId) -> int:
        """Only paid-out referrals. Drives the `Registrations` counter and
        the milestone calculation."""
        ...

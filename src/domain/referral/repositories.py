from typing import Protocol

from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId


class IReferralRepository(Protocol):
    async def add(self, referral: Referral) -> None: ...

    async def exists_for_referee(self, referee_id: UserId) -> bool: ...

    async def count_for_referrer(self, referrer_id: UserId) -> int: ...

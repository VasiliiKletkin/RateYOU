from typing import Protocol

from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId


class IReferralRepository(Protocol):
    async def add(self, referral: Referral) -> None: ...

    async def get_by_referee(self, referee_id: UserId) -> Referral | None: ...

    async def list_by_referrer(self, referrer_id: UserId) -> list[Referral]: ...

    async def update(self, referral: Referral) -> None: ...

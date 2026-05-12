from datetime import datetime
from typing import Protocol

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription


class ISubscriptionRepository(Protocol):
    async def add(self, grant: Subscription) -> None: ...

    async def list_for(self, owner_id: UserId) -> list[Subscription]: ...

    async def list_active_purchases_for(
        self,
        owner_id: UserId,
        now: datetime,
    ) -> list[Subscription]: ...

    async def find_by_transaction(
        self,
        transaction_id: TransactionId,
    ) -> Subscription | None: ...

    async def update(self, grant: Subscription) -> None: ...

from datetime import datetime
from typing import Protocol

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant


class ISubscriptionRepository(Protocol):
    async def add(self, grant: SubscriptionGrant) -> None: ...

    async def list_for(self, owner_id: UserId) -> list[SubscriptionGrant]: ...

    async def list_active_purchases_for(
        self,
        owner_id: UserId,
        now: datetime,
    ) -> list[SubscriptionGrant]: ...

    async def find_by_transaction(
        self,
        transaction_id: TransactionId,
    ) -> SubscriptionGrant | None: ...

    async def update(self, grant: SubscriptionGrant) -> None: ...

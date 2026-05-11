from typing import Protocol

from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription


class ISubscriptionRepository(Protocol):
    async def add(self, subscription: Subscription) -> None: ...

    async def get_for(self, owner_id: UserId) -> Subscription | None: ...

    async def update(self, subscription: Subscription) -> None: ...

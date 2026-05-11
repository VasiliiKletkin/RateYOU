from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.infrastructure.db.mappers.subscription import (
    orm_to_subscription,
    subscription_to_orm,
)
from src.infrastructure.db.models.subscription import SubscriptionORM


@dataclass
class SubscriptionRepository:
    session: AsyncSession

    async def add(self, subscription: Subscription) -> None:
        self.session.add(subscription_to_orm(subscription))
        await self.session.flush()

    async def get_for(self, owner_id: UserId) -> Subscription | None:
        orm = await self.session.get(SubscriptionORM, owner_id.value)
        return orm_to_subscription(orm) if orm is not None else None

    async def update(self, subscription: Subscription) -> None:
        existing = await self.session.get(SubscriptionORM, subscription.owner_id.value)
        if existing is None:
            raise ValueError(
                f"Subscription for {subscription.owner_id.value} not found for update"
            )
        existing.tier = subscription.tier.value
        existing.expires_at = subscription.expires_at
        existing.is_revoked = subscription.is_revoked
        existing.updated_at = subscription.updated_at
        await self.session.flush()

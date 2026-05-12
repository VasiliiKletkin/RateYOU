from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionSource
from src.infrastructure.db.mappers.subscription import (
    orm_to_subscription,
    subscription_to_orm,
)
from src.infrastructure.db.models.subscription import SubscriptionORM


@dataclass
class SubscriptionRepository:
    session: AsyncSession

    async def add(self, grant: Subscription) -> None:
        self.session.add(subscription_to_orm(grant))
        await self.session.flush()

    async def list_for(self, owner_id: UserId) -> list[Subscription]:
        stmt = (
            select(SubscriptionORM)
            .where(SubscriptionORM.owner_id == owner_id.value)
            .order_by(SubscriptionORM.created_at.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [orm_to_subscription(r) for r in rows]

    async def list_active_purchases_for(
        self,
        owner_id: UserId,
        now: datetime,
    ) -> list[Subscription]:
        stmt = select(SubscriptionORM).where(
            SubscriptionORM.owner_id == owner_id.value,
            SubscriptionORM.source == SubscriptionSource.PURCHASE,
            SubscriptionORM.is_revoked.is_(False),
            SubscriptionORM.expires_at > now,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [orm_to_subscription(r) for r in rows]

    async def find_by_transaction(
        self,
        transaction_id: TransactionId,
    ) -> Subscription | None:
        stmt = select(SubscriptionORM).where(
            SubscriptionORM.transaction_id == transaction_id.value
        )
        orm = (await self.session.execute(stmt)).scalar_one_or_none()
        return orm_to_subscription(orm) if orm is not None else None

    async def update(self, grant: Subscription) -> None:
        existing = await self.session.get(SubscriptionORM, grant.id.value)
        if existing is None:
            raise ValueError(
                f"Subscription {grant.id.value} not found for update"
            )
        existing.tier = grant.tier
        existing.source = grant.source
        existing.transaction_id = (
            grant.transaction_id.value if grant.transaction_id is not None else None
        )
        existing.starts_at = grant.starts_at
        existing.expires_at = grant.expires_at
        existing.is_revoked = grant.is_revoked
        await self.session.flush()

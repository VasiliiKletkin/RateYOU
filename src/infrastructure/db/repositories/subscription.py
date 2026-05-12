from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.value_objects import GrantSource
from src.infrastructure.db.mappers.subscription import (
    grant_to_orm,
    orm_to_grant,
)
from src.infrastructure.db.models.subscription import SubscriptionGrantORM


@dataclass
class SubscriptionRepository:
    session: AsyncSession

    async def add(self, grant: SubscriptionGrant) -> None:
        self.session.add(grant_to_orm(grant))
        await self.session.flush()

    async def list_for(self, owner_id: UserId) -> list[SubscriptionGrant]:
        stmt = (
            select(SubscriptionGrantORM)
            .where(SubscriptionGrantORM.owner_id == owner_id.value)
            .order_by(SubscriptionGrantORM.created_at.asc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [orm_to_grant(r) for r in rows]

    async def list_active_purchases_for(
        self,
        owner_id: UserId,
        now: datetime,
    ) -> list[SubscriptionGrant]:
        stmt = select(SubscriptionGrantORM).where(
            SubscriptionGrantORM.owner_id == owner_id.value,
            SubscriptionGrantORM.source == GrantSource.PURCHASE.value,
            SubscriptionGrantORM.is_revoked.is_(False),
            SubscriptionGrantORM.expires_at > now,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [orm_to_grant(r) for r in rows]

    async def find_by_transaction(
        self,
        transaction_id: TransactionId,
    ) -> SubscriptionGrant | None:
        stmt = select(SubscriptionGrantORM).where(
            SubscriptionGrantORM.transaction_id == transaction_id.value
        )
        orm = (await self.session.execute(stmt)).scalar_one_or_none()
        return orm_to_grant(orm) if orm is not None else None

    async def update(self, grant: SubscriptionGrant) -> None:
        existing = await self.session.get(SubscriptionGrantORM, grant.id.value)
        if existing is None:
            raise ValueError(
                f"SubscriptionGrant {grant.id.value} not found for update"
            )
        existing.tier = grant.tier.value
        existing.source = grant.source.value
        existing.transaction_id = (
            grant.transaction_id.value if grant.transaction_id is not None else None
        )
        existing.starts_at = grant.starts_at
        existing.expires_at = grant.expires_at
        existing.is_revoked = grant.is_revoked
        await self.session.flush()

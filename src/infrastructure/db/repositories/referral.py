from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.referral import (
    orm_to_referral,
    referral_to_orm,
)
from src.infrastructure.db.models.referral import ReferralORM


@dataclass
class ReferralRepository:
    session: AsyncSession

    async def add(self, referral: Referral) -> None:
        self.session.add(referral_to_orm(referral))
        await self.session.flush()

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        stmt = select(ReferralORM).where(ReferralORM.referee_id == referee_id.value)
        orm = (await self.session.execute(stmt)).scalar_one_or_none()
        return orm_to_referral(orm) if orm is not None else None

    async def update(self, referral: Referral) -> None:
        existing = await self.session.get(ReferralORM, referral.id.value)
        if existing is None:
            raise ValueError(f"Referral {referral.id.value} not found for update")
        existing.rewarded_at = referral.rewarded_at
        await self.session.flush()

    async def count_total_for_referrer(self, referrer_id: UserId) -> int:
        stmt = select(func.count(ReferralORM.id)).where(
            ReferralORM.referrer_id == referrer_id.value
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_rewarded_for_referrer(self, referrer_id: UserId) -> int:
        stmt = select(func.count(ReferralORM.id)).where(
            ReferralORM.referrer_id == referrer_id.value,
            ReferralORM.rewarded_at.is_not(None),
        )
        return int((await self.session.execute(stmt)).scalar_one())

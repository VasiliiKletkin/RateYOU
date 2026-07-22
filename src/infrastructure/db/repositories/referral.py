from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.referral.entities import Referral
from src.domain.referral.value_objects import ReferralId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.referral import ReferralORM


@dataclass
class ReferralRepository:
    session: AsyncSession

    async def add(self, referral: Referral) -> None:
        self.session.add(
            ReferralORM(
                id=referral.id.value,
                referrer_id=referral.referrer_id.value,
                referee_id=referral.referee_id.value,
                created_at=referral.created_at,
                rewarded_at=referral.rewarded_at,
            )
        )
        await self.session.flush()

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        stmt = select(ReferralORM).where(ReferralORM.referee_id == referee_id.value)
        orm = (await self.session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return Referral(
            id=ReferralId(orm.id),
            referrer_id=UserId(orm.referrer_id),
            referee_id=UserId(orm.referee_id),
            created_at=orm.created_at,
            rewarded_at=orm.rewarded_at,
        )

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

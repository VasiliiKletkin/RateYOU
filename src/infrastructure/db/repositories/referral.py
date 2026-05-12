from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.mappers.referral import referral_to_orm
from src.infrastructure.db.models.referral import ReferralORM


@dataclass
class ReferralRepository:
    session: AsyncSession

    async def add(self, referral: Referral) -> None:
        self.session.add(referral_to_orm(referral))
        await self.session.flush()

    async def exists_for_referee(self, referee_id: UserId) -> bool:
        stmt = select(ReferralORM.id).where(
            ReferralORM.referee_id == referee_id.value
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def count_for_referrer(self, referrer_id: UserId) -> int:
        stmt = select(func.count(ReferralORM.id)).where(
            ReferralORM.referrer_id == referrer_id.value
        )
        return int((await self.session.execute(stmt)).scalar_one())

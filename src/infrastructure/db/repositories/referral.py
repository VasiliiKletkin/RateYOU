from dataclasses import dataclass

from sqlalchemy import select
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
        result = await self.session.execute(
            select(ReferralORM).where(
                ReferralORM.referee_id == referee_id.value
            )
        )
        orm = result.scalar_one_or_none()
        return orm_to_referral(orm) if orm is not None else None

    async def list_by_referrer(
        self, referrer_id: UserId
    ) -> list[Referral]:
        stmt = (
            select(ReferralORM)
            .where(ReferralORM.referrer_id == referrer_id.value)
            .order_by(ReferralORM.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [orm_to_referral(r) for r in rows]

    async def update(self, referral: Referral) -> None:
        existing = await self.session.get(ReferralORM, referral.id.value)
        if existing is None:
            raise ValueError(
                f"Referral {referral.id.value} not found for update"
            )
        existing.status = referral.status.value
        existing.profile_created = referral.profile_created
        existing.first_rating_given = referral.first_rating_given
        existing.qualified_at = referral.qualified_at
        existing.rewarded_at = referral.rewarded_at
        await self.session.flush()

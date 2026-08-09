from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.referral.entities import Referral
from src.domain.referral.value_objects import ReferralId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.identity import (
    AcquisitionORM,
    AcquisitionSourceORM,
    UserORM,
)
from src.infrastructure.db.repositories.acquisition import get_or_create_source_id


@dataclass
class ReferralRepository:
    """The Referral aggregate persisted over the unified acquisition tables.

    There is no `referrals` table anymore: a referral IS an acquisition
    whose source is a person (`acquisition_sources.referrer_id` set, code =
    the referrer's telegram_id — exactly what the deep link carries), and
    the reward lifecycle lives in `acquisitions.rewarded_at`.

    `ReferralId` is the referee's user UUID: `referee_id` was UNIQUE in the
    old table and is the PK of `acquisitions` now, so it identifies the
    referral just as well — `Referral.create_pending`'s freshly generated
    id is deliberately not persisted.
    """

    session: AsyncSession

    async def add(self, referral: Referral) -> None:
        referrer = await self.session.get(UserORM, referral.referrer_id.value)
        if referrer is None:
            raise ValueError(f"User {referral.referrer_id.value} not found to create referral")
        source_id = await get_or_create_source_id(
            self.session,
            code=str(referrer.telegram_id),
            referrer_id=referral.referrer_id.value,
        )
        self.session.add(
            AcquisitionORM(
                user_id=referral.referee_id.value,
                source_id=source_id,
                created_at=referral.created_at,
                rewarded_at=referral.rewarded_at,
            )
        )
        await self.session.flush()

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        row = (await self.session.execute(self._referral_stmt(referee_id))).one_or_none()
        if row is None:
            return None
        link, referrer_id = row
        return Referral(
            id=ReferralId(link.user_id),
            referrer_id=UserId(referrer_id),
            referee_id=UserId(link.user_id),
            created_at=link.created_at,
            rewarded_at=link.rewarded_at,
        )

    async def update(self, referral: Referral) -> None:
        row = (await self.session.execute(self._referral_stmt(referral.referee_id))).one_or_none()
        if row is None:
            raise ValueError(f"Referral {referral.id.value} not found for update")
        link, _ = row
        link.rewarded_at = referral.rewarded_at
        await self.session.flush()

    async def count_total_for_referrer(self, referrer_id: UserId) -> int:
        return await self._count_for_referrer(referrer_id, rewarded_only=False)

    async def count_rewarded_for_referrer(self, referrer_id: UserId) -> int:
        return await self._count_for_referrer(referrer_id, rewarded_only=True)

    @staticmethod
    def _referral_stmt(
        referee_id: UserId,
    ) -> Select[tuple[AcquisitionORM, UUID | None]]:
        return (
            select(AcquisitionORM, AcquisitionSourceORM.referrer_id)
            .join(
                AcquisitionSourceORM,
                AcquisitionSourceORM.id == AcquisitionORM.source_id,
            )
            .where(
                AcquisitionORM.user_id == referee_id.value,
                AcquisitionSourceORM.referrer_id.is_not(None),
            )
        )

    async def _count_for_referrer(self, referrer_id: UserId, *, rewarded_only: bool) -> int:
        stmt = (
            select(func.count(AcquisitionORM.user_id))
            .join(
                AcquisitionSourceORM,
                AcquisitionSourceORM.id == AcquisitionORM.source_id,
            )
            .where(AcquisitionSourceORM.referrer_id == referrer_id.value)
        )
        if rewarded_only:
            stmt = stmt.where(AcquisitionORM.rewarded_at.is_not(None))
        return int((await self.session.execute(stmt)).scalar_one())

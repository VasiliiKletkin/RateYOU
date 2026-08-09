from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import Acquisition
from src.domain.identity.value_objects import AcquisitionSource
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.identity import AcquisitionORM, AcquisitionSourceORM


async def get_or_create_source_id(
    session: AsyncSession,
    code: str,
    referrer_id: UUID | None = None,
) -> UUID:
    """Race-safe get-or-create for the source dictionary.

    Shared by AcquisitionRepository (campaign tags) and ReferralRepository
    (person-sources, `referrer_id` set). Two users can arrive from a
    brand-new source simultaneously: `ON CONFLICT DO NOTHING` lets the
    loser of the unique-index race fall through to the SELECT instead of
    erroring the registration.
    """
    insert_stmt = (
        pg_insert(AcquisitionSourceORM)
        .values(id=uuid4(), code=code, referrer_id=referrer_id)
        .on_conflict_do_nothing(index_elements=["code"])
        .returning(AcquisitionSourceORM.id)
    )
    inserted = (await session.execute(insert_stmt)).scalar_one_or_none()
    if inserted is not None:
        return inserted
    existing = await session.execute(
        select(AcquisitionSourceORM.id).where(AcquisitionSourceORM.code == code)
    )
    return existing.scalar_one()


@dataclass
class AcquisitionRepository:
    """Maps the flat domain `Acquisition` onto the normalised pair of tables.

    The domain sees `Acquisition(user_id, source, created_at)`; storage is a
    dictionary (`acquisition_sources`) plus a link row (`acquisitions`).
    The split stays entirely on this side of the boundary.
    """

    session: AsyncSession

    async def add(self, acquisition: Acquisition) -> None:
        source_id = await get_or_create_source_id(self.session, code=acquisition.source.value)
        self.session.add(
            AcquisitionORM(
                user_id=acquisition.user_id.value,
                source_id=source_id,
                created_at=acquisition.created_at,
            )
        )
        await self.session.flush()

    async def get_for(self, user_id: UserId) -> Acquisition | None:
        stmt = (
            select(AcquisitionORM, AcquisitionSourceORM.code)
            .join(
                AcquisitionSourceORM,
                AcquisitionSourceORM.id == AcquisitionORM.source_id,
            )
            .where(AcquisitionORM.user_id == user_id.value)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        link, code = row
        return Acquisition(
            user_id=UserId(link.user_id),
            source=AcquisitionSource(code),
            created_at=link.created_at,
        )

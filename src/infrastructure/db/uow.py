from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class SqlAlchemyUnitOfWork:
    """Concrete UnitOfWork backed by an AsyncSession.

    Conforms structurally to domain.shared.uow.UnitOfWork.
    """

    session: AsyncSession

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

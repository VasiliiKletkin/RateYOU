from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.shared.uow import UnitOfWork
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork


class UoWProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def uow(self, session: AsyncSession) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session=session)

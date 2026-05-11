from typing import Protocol


class UnitOfWork(Protocol):
    """Transaction boundary. Use cases hold one and call commit() to persist.

    Implemented by infrastructure/db/uow.SqlAlchemyUnitOfWork.
    """

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

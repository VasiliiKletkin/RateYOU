from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.config import Settings


class DbProvider(Provider):
    @provide(scope=Scope.APP)
    async def engine(self, settings: Settings) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(settings.postgres.dsn)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def session_factory(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with factory() as session:
            yield session

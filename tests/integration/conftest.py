from collections.abc import AsyncIterator

import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.config import get_settings
from src.infrastructure.db.models import Base


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Fresh engine per test. Session-scope causes loop-scope mismatches with asyncpg."""
    eng = create_async_engine(get_settings().postgres.dsn)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yields a session and truncates all tables after the test."""
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """Yields a Redis client and cleans up keys we use after the test."""
    r = Redis.from_url(get_settings().redis.dsn)
    try:
        yield r
    finally:
        for pattern in ("skipped:*", "throttle:*"):
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
        await r.aclose()

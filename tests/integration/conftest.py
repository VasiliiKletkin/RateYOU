import asyncio
import subprocess
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.config import PostgresConfig, get_settings
from src.infrastructure.db.models import Base


async def _create_database_if_missing(pg: PostgresConfig) -> None:
    """CREATE DATABASE <pg.db> if it doesn't exist.

    Connects to the maintenance DB `postgres` because CREATE DATABASE can't
    run inside a transaction or against the target DB itself.
    """
    admin = await asyncpg.connect(
        host=pg.host,
        port=pg.port,
        user=pg.user,
        password=pg.password.get_secret_value(),
        database="postgres",
    )
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", pg.db)
        if exists is None:
            await admin.execute(f'CREATE DATABASE "{pg.db}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_test_database() -> None:
    """Create the test DB and run Alembic up to head once per session.

    `POSTGRES_DB` is forced to a test value via [tool.pytest.ini_options].env
    in pyproject.toml — this fixture just ensures the target exists and is
    on the latest schema before any test runs. The 'test' guard prevents an
    accidental run against the dev DB if pyproject is misconfigured.
    """
    pg = get_settings().postgres
    if "test" not in pg.db:
        raise RuntimeError(
            f"Refusing to bootstrap a non-test database: POSTGRES_DB={pg.db!r}. "
            "Tests must run against a database whose name contains 'test'."
        )
    asyncio.run(_create_database_if_missing(pg))
    subprocess.run(["alembic", "upgrade", "head"], check=True)


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

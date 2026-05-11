from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import Role, TelegramId
from src.infrastructure.db.repositories.user import UserRepository


async def test_add_and_get_by_telegram_id_roundtrip(session: AsyncSession) -> None:
    repo = UserRepository(session=session)
    now = datetime.now(UTC)
    user = User.register(TelegramId(99999), now)

    await repo.add(user)

    found = await repo.get_by_telegram_id(TelegramId(99999))
    assert found is not None
    assert found.id == user.id
    assert found.telegram_id == user.telegram_id
    assert found.role == Role.USER
    assert found.is_banned is False
    assert found.created_at == user.created_at


async def test_get_by_telegram_id_returns_none_when_missing(session: AsyncSession) -> None:
    repo = UserRepository(session=session)
    found = await repo.get_by_telegram_id(TelegramId(424242))
    assert found is None


async def test_get_by_id_roundtrip(session: AsyncSession) -> None:
    repo = UserRepository(session=session)
    user = User.register(TelegramId(1234), datetime.now(UTC))
    await repo.add(user)

    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.id == user.id


async def test_update_persists_ban_state(session: AsyncSession) -> None:
    repo = UserRepository(session=session)
    now = datetime.now(UTC)
    user = User.register(TelegramId(7777), now)
    await repo.add(user)

    user.ban("spam", now=now)
    await repo.update(user)

    refreshed = await repo.get_by_id(user.id)
    assert refreshed is not None
    assert refreshed.is_banned is True
    assert refreshed.ban_reason == "spam"
    assert refreshed.banned_at == now

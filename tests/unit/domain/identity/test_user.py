from datetime import UTC, datetime

import pytest

from src.domain.identity.entities import User
from src.domain.identity.exceptions import InvalidBanReason, UserIsBanned
from src.domain.identity.value_objects import Role, TelegramId


def test_register_creates_active_user() -> None:
    now = datetime.now(UTC)
    user = User.register(telegram_id=TelegramId(12345), now=now)

    assert user.telegram_id == TelegramId(12345)
    assert user.role == Role.USER
    assert user.is_banned is False
    assert user.ban_reason is None
    assert user.banned_at is None
    assert user.created_at == now


def test_register_generates_unique_ids() -> None:
    now = datetime.now(UTC)
    u1 = User.register(TelegramId(1), now)
    u2 = User.register(TelegramId(2), now)
    assert u1.id != u2.id


def test_ban_marks_user_banned() -> None:
    now = datetime.now(UTC)
    user = User.register(TelegramId(1), now)
    user.ban("spam", now=now)

    assert user.is_banned is True
    assert user.ban_reason == "spam"
    assert user.banned_at == now


def test_ban_trims_reason_whitespace() -> None:
    user = User.register(TelegramId(1), datetime.now(UTC))
    user.ban("   spam   ", now=datetime.now(UTC))
    assert user.ban_reason == "spam"


def test_ban_with_empty_reason_raises() -> None:
    user = User.register(TelegramId(1), datetime.now(UTC))
    with pytest.raises(InvalidBanReason):
        user.ban("   ", now=datetime.now(UTC))


def test_unban_clears_state() -> None:
    now = datetime.now(UTC)
    user = User.register(TelegramId(1), now)
    user.ban("spam", now=now)
    user.unban()

    assert user.is_banned is False
    assert user.ban_reason is None
    assert user.banned_at is None


def test_ensure_active_passes_for_unbanned() -> None:
    user = User.register(TelegramId(1), datetime.now(UTC))
    user.ensure_active()  # must not raise


def test_ensure_active_raises_for_banned() -> None:
    user = User.register(TelegramId(1), datetime.now(UTC))
    user.ban("spam", now=datetime.now(UTC))
    with pytest.raises(UserIsBanned):
        user.ensure_active()


def test_telegram_id_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        TelegramId(0)
    with pytest.raises(ValueError, match="must be positive"):
        TelegramId(-1)


def test_telegram_id_accepts_large_values() -> None:
    assert TelegramId(1).value == 1
    assert TelegramId(1_000_000_000_000).value == 1_000_000_000_000


def test_admin_is_admin_property() -> None:
    user = User.register(TelegramId(1), datetime.now(UTC))
    assert user.is_admin is False
    user.role = Role.ADMIN
    assert user.is_admin is True

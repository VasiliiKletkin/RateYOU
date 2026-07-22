"""Covers the Redis-backed bookkeeping of the new-profile broadcast.

The task module itself needs a live broker at import time only for the
decorator; the helpers under test are plain async functions, so a tiny fake
Redis is enough — no worker, no Telegram.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from src.presentation.tasks.broadcast import (
    _claim_cooldown,
    _read_watermark,
    _write_watermark,
)


@dataclass
class FakeRedis:
    """Implements just enough of `set`/`get`, including NX semantics."""

    store: dict[str, str] = field(default_factory=dict)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
        **_: Any,
    ) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


async def test_first_claim_wins_and_second_is_refused() -> None:
    redis = FakeRedis()
    user_id = uuid4()

    assert await _claim_cooldown(redis, user_id) is True  # type: ignore[arg-type]
    assert await _claim_cooldown(redis, user_id) is False  # type: ignore[arg-type]


async def test_cooldown_is_per_user() -> None:
    redis = FakeRedis()

    assert await _claim_cooldown(redis, uuid4()) is True  # type: ignore[arg-type]
    assert await _claim_cooldown(redis, uuid4()) is True  # type: ignore[arg-type]


async def test_missing_watermark_falls_back_to_a_day_ago() -> None:
    """First run must not announce every profile ever created."""
    redis = FakeRedis()

    since = await _read_watermark(redis)  # type: ignore[arg-type]

    assert timedelta(hours=23) < datetime.now(UTC) - since < timedelta(hours=25)


async def test_watermark_roundtrips() -> None:
    redis = FakeRedis()
    moment = datetime.now(UTC) - timedelta(hours=3)

    await _write_watermark(redis, moment)  # type: ignore[arg-type]

    assert await _read_watermark(redis) == moment  # type: ignore[arg-type]


async def test_corrupt_watermark_falls_back_instead_of_crashing() -> None:
    redis = FakeRedis(store={"broadcast:new_profiles:last_run_at": "not-a-date"})

    since = await _read_watermark(redis)  # type: ignore[arg-type]

    assert timedelta(hours=23) < datetime.now(UTC) - since < timedelta(hours=25)

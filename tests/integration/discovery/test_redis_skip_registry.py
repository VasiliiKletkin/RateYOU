"""Integration tests for RedisSkipRegistry against a real Redis."""

import asyncio

from redis.asyncio import Redis

from src.domain.shared.identifiers import UserId
from src.infrastructure.discovery.redis_skip_registry import RedisSkipRegistry


async def test_record_skip_and_get_back(redis_client: Redis) -> None:
    registry = RedisSkipRegistry(redis=redis_client, ttl_seconds=60)
    viewer = UserId.new()
    skipped = UserId.new()

    await registry.record_skip(viewer, skipped)

    members = await registry.get_skipped(viewer)
    assert members == [skipped]


async def test_get_skipped_returns_empty_for_unknown_viewer(redis_client: Redis) -> None:
    registry = RedisSkipRegistry(redis=redis_client, ttl_seconds=60)
    assert await registry.get_skipped(UserId.new()) == []


async def test_record_multiple_skips_for_one_viewer(redis_client: Redis) -> None:
    registry = RedisSkipRegistry(redis=redis_client, ttl_seconds=60)
    viewer = UserId.new()
    s1 = UserId.new()
    s2 = UserId.new()
    s3 = UserId.new()

    await registry.record_skip(viewer, s1)
    await registry.record_skip(viewer, s2)
    await registry.record_skip(viewer, s3)

    members = set(await registry.get_skipped(viewer))
    assert members == {s1, s2, s3}


async def test_skips_are_isolated_per_viewer(redis_client: Redis) -> None:
    registry = RedisSkipRegistry(redis=redis_client, ttl_seconds=60)
    viewer_a = UserId.new()
    viewer_b = UserId.new()
    skipped_for_a = UserId.new()
    skipped_for_b = UserId.new()

    await registry.record_skip(viewer_a, skipped_for_a)
    await registry.record_skip(viewer_b, skipped_for_b)

    assert await registry.get_skipped(viewer_a) == [skipped_for_a]
    assert await registry.get_skipped(viewer_b) == [skipped_for_b]


async def test_ttl_expires_skip_entry(redis_client: Redis) -> None:
    registry = RedisSkipRegistry(redis=redis_client, ttl_seconds=1)
    viewer = UserId.new()
    skipped = UserId.new()

    await registry.record_skip(viewer, skipped)
    await asyncio.sleep(1.5)

    assert await registry.get_skipped(viewer) == []

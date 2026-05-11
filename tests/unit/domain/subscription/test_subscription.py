from datetime import UTC, datetime, timedelta

from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import Tier


def test_activate_sets_expiry_from_now_plus_duration() -> None:
    now = datetime.now(UTC)
    owner = UserId.new()

    sub = Subscription.activate(owner, Tier.BRONZE, duration_days=7, now=now)

    assert sub.owner_id == owner
    assert sub.tier == Tier.BRONZE
    assert sub.expires_at == now + timedelta(days=7)
    assert sub.is_revoked is False
    assert sub.is_active_at(now) is True


def test_is_active_at_returns_false_for_expired() -> None:
    now = datetime.now(UTC)
    sub = Subscription.activate(UserId.new(), Tier.BRONZE, duration_days=7, now=now)

    later = now + timedelta(days=8)

    assert sub.is_active_at(later) is False


def test_is_active_at_returns_false_for_revoked() -> None:
    now = datetime.now(UTC)
    sub = Subscription.activate(UserId.new(), Tier.GOLD, duration_days=30, now=now)
    sub.revoke(now=now)

    assert sub.is_active_at(now) is False


def test_renew_or_upgrade_replaces_period_and_tier() -> None:
    now = datetime.now(UTC)
    sub = Subscription.activate(UserId.new(), Tier.BRONZE, duration_days=7, now=now)
    later = now + timedelta(days=3)

    sub.renew_or_upgrade(Tier.GOLD, duration_days=30, now=later)

    assert sub.tier == Tier.GOLD
    assert sub.expires_at == later + timedelta(days=30)  # NOT old + 30 — replace policy
    assert sub.is_revoked is False


def test_renew_reactivates_revoked() -> None:
    now = datetime.now(UTC)
    sub = Subscription.activate(UserId.new(), Tier.SILVER, duration_days=30, now=now)
    sub.revoke(now=now)
    assert sub.is_revoked is True

    later = now + timedelta(hours=1)
    sub.renew_or_upgrade(Tier.SILVER, duration_days=30, now=later)

    assert sub.is_revoked is False
    assert sub.is_active_at(later) is True


def test_revoke_sets_expires_at_to_now_and_marks_revoked() -> None:
    now = datetime.now(UTC)
    sub = Subscription.activate(UserId.new(), Tier.GOLD, duration_days=30, now=now)
    later = now + timedelta(days=5)

    sub.revoke(now=later)

    assert sub.is_revoked is True
    assert sub.expires_at == later

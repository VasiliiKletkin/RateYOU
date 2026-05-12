from datetime import UTC, datetime, timedelta

from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription, SubscriptionStatus
from src.domain.subscription.value_objects import SubscriptionSource, Tier


def test_create_purchase_sets_fields_and_expiry() -> None:
    now = datetime.now(UTC)
    owner = UserId.new()
    tx = TransactionId.new()

    grant = Subscription.create_purchase(
        owner_id=owner,
        tier=Tier.BRONZE,
        duration_days=7,
        transaction_id=tx,
        now=now,
    )

    assert grant.owner_id == owner
    assert grant.tier == Tier.BRONZE
    assert grant.source == SubscriptionSource.PURCHASE
    assert grant.transaction_id == tx
    assert grant.starts_at == now
    assert grant.expires_at == now + timedelta(days=7)
    assert grant.is_revoked is False
    assert grant.is_active_at(now) is True


def test_create_bonus_uses_bonus_tier_and_no_transaction() -> None:
    now = datetime.now(UTC)
    grant = Subscription.create_bonus(
        owner_id=UserId.new(), duration_days=3, now=now
    )

    assert grant.tier == Tier.BONUS
    assert grant.source == SubscriptionSource.BONUS
    assert grant.transaction_id is None
    assert grant.expires_at == now + timedelta(days=3)


def test_is_active_at_returns_false_when_expired() -> None:
    now = datetime.now(UTC)
    grant = Subscription.create_purchase(
        UserId.new(), Tier.BRONZE, duration_days=7,
        transaction_id=None, now=now,
    )

    assert grant.is_active_at(now + timedelta(days=8)) is False


def test_is_active_at_returns_false_when_revoked() -> None:
    now = datetime.now(UTC)
    grant = Subscription.create_purchase(
        UserId.new(), Tier.GOLD, duration_days=30,
        transaction_id=None, now=now,
    )
    grant.revoke(now=now)

    assert grant.is_active_at(now) is False
    assert grant.is_revoked is True
    assert grant.expires_at == now


def test_status_from_no_grants_is_inactive() -> None:
    status = SubscriptionStatus.from_grants([], datetime.now(UTC))

    assert status.is_active is False
    assert status.tier is None
    assert status.expires_at is None


def test_status_picks_highest_priority_tier_among_active() -> None:
    now = datetime.now(UTC)
    owner = UserId.new()
    bronze = Subscription.create_purchase(
        owner, Tier.BRONZE, duration_days=7, transaction_id=None, now=now,
    )
    bonus = Subscription.create_bonus(owner, duration_days=3, now=now)

    status = SubscriptionStatus.from_grants([bronze, bonus], now)

    # BRONZE > BONUS in priority
    assert status.is_active is True
    assert status.tier == Tier.BRONZE
    # expires_at is the LATEST among actives — bronze (7d) > bonus (3d)
    assert status.expires_at == bronze.expires_at


def test_status_ignores_revoked_grants() -> None:
    now = datetime.now(UTC)
    owner = UserId.new()
    revoked_gold = Subscription.create_purchase(
        owner, Tier.GOLD, duration_days=30, transaction_id=None, now=now,
    )
    revoked_gold.revoke(now=now)
    live_bronze = Subscription.create_purchase(
        owner, Tier.BRONZE, duration_days=7, transaction_id=None, now=now,
    )

    status = SubscriptionStatus.from_grants([revoked_gold, live_bronze], now)

    assert status.is_active is True
    assert status.tier == Tier.BRONZE


def test_status_ignores_expired_grants() -> None:
    now = datetime.now(UTC)
    long_ago = now - timedelta(days=60)
    owner = UserId.new()
    expired = Subscription.create_purchase(
        owner, Tier.GOLD, duration_days=30,
        transaction_id=None, now=long_ago,
    )
    fresh_bonus = Subscription.create_bonus(owner, duration_days=3, now=now)

    status = SubscriptionStatus.from_grants([expired, fresh_bonus], now)

    assert status.is_active is True
    assert status.tier == Tier.BONUS
    assert status.expires_at == fresh_bonus.expires_at

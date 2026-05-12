from datetime import UTC, datetime, timedelta

import pytest

from src.domain.referral.entities import Referral
from src.domain.referral.exceptions import SelfReferral
from src.domain.shared.identifiers import UserId


def test_create_pending_sets_fields_with_no_reward() -> None:
    now = datetime.now(UTC)
    referrer = UserId.new()
    referee = UserId.new()

    r = Referral.create_pending(referrer, referee, now)

    assert r.referrer_id == referrer
    assert r.referee_id == referee
    assert r.created_at == now
    assert r.rewarded_at is None
    assert r.is_rewarded is False


def test_self_referral_is_rejected() -> None:
    same = UserId.new()
    with pytest.raises(SelfReferral):
        Referral.create_pending(same, same, datetime.now(UTC))


def test_mark_rewarded_sets_timestamp() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)
    later = now + timedelta(hours=1)

    r.mark_rewarded(later)

    assert r.rewarded_at == later
    assert r.is_rewarded is True


def test_mark_rewarded_is_idempotent() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)
    first = now + timedelta(hours=1)
    second = now + timedelta(hours=2)

    r.mark_rewarded(first)
    r.mark_rewarded(second)  # repeated call — no change

    assert r.rewarded_at == first


def test_each_pending_gets_unique_id() -> None:
    now = datetime.now(UTC)
    r1 = Referral.create_pending(UserId.new(), UserId.new(), now)
    r2 = Referral.create_pending(UserId.new(), UserId.new(), now)

    assert r1.id != r2.id

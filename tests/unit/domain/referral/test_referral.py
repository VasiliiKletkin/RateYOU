from datetime import UTC, datetime, timedelta

import pytest

from src.domain.referral.entities import Referral
from src.domain.referral.exceptions import (
    InvalidReferralStatusTransition,
    SelfReferral,
)
from src.domain.referral.value_objects import ReferralStatus
from src.domain.shared.identifiers import UserId


def test_create_pending_initializes_flags_to_false() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)

    assert r.status == ReferralStatus.PENDING
    assert r.profile_created is False
    assert r.first_rating_given is False
    assert r.qualified_at is None
    assert r.rewarded_at is None
    assert r.created_at == now


def test_self_referral_is_rejected() -> None:
    same = UserId.new()
    with pytest.raises(SelfReferral):
        Referral.create_pending(same, same, datetime.now(UTC))


def test_profile_then_rating_qualifies_on_second_signal() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)

    qualified = r.mark_profile_created(now)
    assert qualified is False
    assert r.status.value == "pending"

    qualified = r.mark_first_rating(now + timedelta(hours=1))
    assert qualified is True
    assert r.status.value == "qualified"
    assert r.qualified_at == now + timedelta(hours=1)


def test_rating_then_profile_also_qualifies() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)

    assert r.mark_first_rating(now) is False
    assert r.mark_profile_created(now) is True
    assert r.status.value == "qualified"


def test_repeated_mark_is_idempotent() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)

    assert r.mark_profile_created(now) is False  # first sets flag
    assert r.mark_profile_created(now) is False  # second is no-op

    # Even after qualifying, repeated marks don't go backwards.
    assert r.mark_first_rating(now) is True
    assert r.mark_first_rating(now) is False
    assert r.mark_profile_created(now) is False


def test_mark_rewarded_advances_state_from_qualified() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)
    r.mark_profile_created(now)
    r.mark_first_rating(now)
    assert r.status.value == "qualified"

    rewarded_at = now + timedelta(seconds=1)
    r.mark_rewarded(rewarded_at)
    assert r.status.value == "rewarded"
    assert r.rewarded_at == rewarded_at


def test_mark_rewarded_from_pending_raises() -> None:
    r = Referral.create_pending(
        UserId.new(), UserId.new(), datetime.now(UTC)
    )
    with pytest.raises(InvalidReferralStatusTransition):
        r.mark_rewarded(datetime.now(UTC))


def test_mark_rewarded_is_idempotent() -> None:
    now = datetime.now(UTC)
    r = Referral.create_pending(UserId.new(), UserId.new(), now)
    r.mark_profile_created(now)
    r.mark_first_rating(now)
    r.mark_rewarded(now)
    first_at = r.rewarded_at

    # Second call doesn't raise and doesn't overwrite the timestamp.
    r.mark_rewarded(now + timedelta(hours=1))
    assert r.rewarded_at == first_at

from datetime import UTC, datetime

import pytest

from src.domain.referral.entities import Referral
from src.domain.referral.exceptions import SelfReferral
from src.domain.shared.identifiers import UserId


def test_reward_sets_fields() -> None:
    now = datetime.now(UTC)
    referrer = UserId.new()
    referee = UserId.new()

    r = Referral.reward(referrer, referee, now)

    assert r.referrer_id == referrer
    assert r.referee_id == referee
    assert r.created_at == now


def test_self_referral_is_rejected() -> None:
    same = UserId.new()
    with pytest.raises(SelfReferral):
        Referral.reward(same, same, datetime.now(UTC))


def test_each_reward_gets_unique_id() -> None:
    now = datetime.now(UTC)
    r1 = Referral.reward(UserId.new(), UserId.new(), now)
    r2 = Referral.reward(UserId.new(), UserId.new(), now)

    assert r1.id != r2.id

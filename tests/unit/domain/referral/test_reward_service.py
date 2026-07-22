from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.services import (
    MILESTONE_BONUS_DAYS,
    MILESTONE_INTERVAL,
    PER_REFERRAL_REWARD_DAYS,
    ReferralRewardService,
)
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionSource, Tier


@dataclass
class FakeReferralRepo:
    referrals: list[Referral] = field(default_factory=list)

    async def add(self, r: Referral) -> None:
        self.referrals.append(r)

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        for r in self.referrals:
            if r.referee_id == referee_id:
                return r
        return None

    async def update(self, r: Referral) -> None:
        for idx, existing in enumerate(self.referrals):
            if existing.id == r.id:
                self.referrals[idx] = r
                return

    async def count_total_for_referrer(self, referrer_id: UserId) -> int:
        return sum(1 for r in self.referrals if r.referrer_id == referrer_id)

    async def count_rewarded_for_referrer(self, referrer_id: UserId) -> int:
        return sum(1 for r in self.referrals if r.referrer_id == referrer_id and r.is_rewarded)


@dataclass
class FakeUserRepo:
    users: dict[UserId, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        return None

    async def update(self, user: User) -> None:
        self.users[user.id] = user

    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return [self.users[uid] for uid in user_ids if uid in self.users]


@dataclass
class FakeSubscriptionRepo:
    grants: list[Subscription] = field(default_factory=list)

    async def add(self, g: Subscription) -> None:
        self.grants.append(g)

    async def list_for(self, owner_id: UserId) -> list[Subscription]:
        return [g for g in self.grants if g.owner_id == owner_id]

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[Subscription]:
        return []

    async def find_by_transaction(self, transaction_id) -> Subscription | None:  # type: ignore[no-untyped-def]
        return None

    async def update(self, g: Subscription) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == g.id:
                self.grants[idx] = g
                return


def _seed_user(repo: FakeUserRepo, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    repo.users[user.id] = user
    return user


async def _seed_pending(
    referrals: FakeReferralRepo,
    referrer: User,
    referee: User,
    now: datetime,
) -> Referral:
    pending = Referral.create_pending(referrer.id, referee.id, now)
    await referrals.add(pending)
    return pending


def _make_service(
    referrals: FakeReferralRepo,
    users: FakeUserRepo,
    subs: FakeSubscriptionRepo,
) -> ReferralRewardService:
    return ReferralRewardService(
        referral_repo=referrals,
        user_repo=users,
        subscription_repo=subs,
    )


async def test_no_op_when_no_pending_referral_exists() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    user = _seed_user(users, 100)
    service = _make_service(referrals, users, subs)

    await service.mark_profile_created(user.id, datetime.now(UTC))

    assert referrals.referrals == []
    assert subs.grants == []


async def test_idempotent_when_referral_already_rewarded() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    referee = _seed_user(users, 200)
    now = datetime.now(UTC)
    pending = await _seed_pending(referrals, referrer, referee, now)
    pending.mark_rewarded(now)
    service = _make_service(referrals, users, subs)

    await service.mark_profile_created(referee.id, now)

    # Still rewarded, no extra grants issued.
    assert referrals.referrals[0].is_rewarded
    assert subs.grants == []


async def test_first_referral_grants_one_day_to_each_side() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    referee = _seed_user(users, 200)
    now = datetime.now(UTC)
    await _seed_pending(referrals, referrer, referee, now)
    service = _make_service(referrals, users, subs)

    await service.mark_profile_created(referee.id, now)

    assert referrals.referrals[0].is_rewarded
    owners = {g.owner_id for g in subs.grants}
    assert owners == {referrer.id, referee.id}
    assert all(g.source == SubscriptionSource.BONUS for g in subs.grants)
    assert all(g.tier == Tier.BONUS for g in subs.grants)
    assert all((g.expires_at - g.starts_at).days == PER_REFERRAL_REWARD_DAYS for g in subs.grants)


async def test_banned_referrer_only_referee_paid() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    referrer.ban("spam", now=datetime.now(UTC))
    referee = _seed_user(users, 200)
    now = datetime.now(UTC)
    await _seed_pending(referrals, referrer, referee, now)
    service = _make_service(referrals, users, subs)

    await service.mark_profile_created(referee.id, now)

    # Referral promoted to rewarded (audit), referee gets paid, referrer skipped.
    assert referrals.referrals[0].is_rewarded
    owners = {g.owner_id for g in subs.grants}
    assert owners == {referee.id}


async def test_third_referral_fires_milestone_bonus() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    service = _make_service(referrals, users, subs)
    now = datetime.now(UTC)

    for tg_id in (200, 201, 202):
        ref = _seed_user(users, tg_id)
        await _seed_pending(referrals, referrer, ref, now)
        await service.mark_profile_created(ref.id, now)

    referrer_grants = [g for g in subs.grants if g.owner_id == referrer.id]
    assert len(referrer_grants) == MILESTONE_INTERVAL + 1
    days = sorted((g.expires_at - g.starts_at).days for g in referrer_grants)
    expected = sorted([PER_REFERRAL_REWARD_DAYS] * MILESTONE_INTERVAL + [MILESTONE_BONUS_DAYS])
    assert days == expected


async def test_no_milestone_before_threshold() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    service = _make_service(referrals, users, subs)
    now = datetime.now(UTC)

    for tg_id in (200, 201):  # 2 < MILESTONE_INTERVAL (3)
        ref = _seed_user(users, tg_id)
        await _seed_pending(referrals, referrer, ref, now)
        await service.mark_profile_created(ref.id, now)

    referrer_grants = [g for g in subs.grants if g.owner_id == referrer.id]
    assert len(referrer_grants) == 2  # base only, no milestone


async def test_sixth_referral_triggers_second_milestone() -> None:
    referrals, users, subs = (
        FakeReferralRepo(),
        FakeUserRepo(),
        FakeSubscriptionRepo(),
    )
    referrer = _seed_user(users, 100)
    service = _make_service(referrals, users, subs)
    now = datetime.now(UTC)

    for i in range(6):
        ref = _seed_user(users, 200 + i)
        await _seed_pending(referrals, referrer, ref, now)
        await service.mark_profile_created(ref.id, now)

    referrer_grants = [g for g in subs.grants if g.owner_id == referrer.id]
    # 6 base + 2 milestones (at #3 and #6)
    assert len(referrer_grants) == 6 + 2
    milestone_grants = [
        g for g in referrer_grants if (g.expires_at - g.starts_at).days == MILESTONE_BONUS_DAYS
    ]
    assert len(milestone_grants) == 2

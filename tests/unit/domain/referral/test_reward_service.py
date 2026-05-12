from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.identity.entities import User
from src.domain.identity.value_objects import ReferralCode, TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.services import (
    REFERRAL_REWARD_DAYS,
    ReferralRewardService,
)
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.value_objects import GrantSource, Tier


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

    async def list_by_referrer(self, referrer_id: UserId) -> list[Referral]:
        return [r for r in self.referrals if r.referrer_id == referrer_id]

    async def update(self, r: Referral) -> None:
        for idx, existing in enumerate(self.referrals):
            if existing.id == r.id:
                self.referrals[idx] = r
                return


@dataclass
class FakeUserRepo:
    users: dict[UserId, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        return None

    async def get_by_referral_code(self, code: ReferralCode) -> User | None:
        return None

    async def update(self, user: User) -> None:
        self.users[user.id] = user


@dataclass
class FakeSubscriptionRepo:
    grants: list[SubscriptionGrant] = field(default_factory=list)

    async def add(self, g: SubscriptionGrant) -> None:
        self.grants.append(g)

    async def list_for(self, owner_id: UserId) -> list[SubscriptionGrant]:
        return [g for g in self.grants if g.owner_id == owner_id]

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[SubscriptionGrant]:
        return []

    async def find_by_transaction(self, transaction_id) -> SubscriptionGrant | None:  # type: ignore[no-untyped-def]
        return None

    async def update(self, g: SubscriptionGrant) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == g.id:
                self.grants[idx] = g
                return


def _seeded_referrer(repo: FakeUserRepo) -> User:
    referrer = User.register(TelegramId(111), datetime.now(UTC))
    repo.users[referrer.id] = referrer
    return referrer


def _make_service(
    referrals: FakeReferralRepo | None = None,
    users: FakeUserRepo | None = None,
    subs: FakeSubscriptionRepo | None = None,
) -> tuple[
    ReferralRewardService,
    FakeReferralRepo,
    FakeUserRepo,
    FakeSubscriptionRepo,
]:
    referrals = referrals or FakeReferralRepo()
    users = users or FakeUserRepo()
    subs = subs or FakeSubscriptionRepo()
    service = ReferralRewardService(
        referral_repo=referrals,
        user_repo=users,
        subscription_repo=subs,
    )
    return service, referrals, users, subs


async def test_mark_calls_are_noop_when_no_referral_exists() -> None:
    service, _, _, subs = _make_service()
    rater = UserId.new()

    await service.mark_first_rating(rater, datetime.now(UTC))
    await service.mark_profile_created(rater, datetime.now(UTC))

    assert subs.grants == []


async def test_full_flow_grants_bonus_to_both_sides() -> None:
    now = datetime.now(UTC)
    referrals_repo = FakeReferralRepo()
    users_repo = FakeUserRepo()
    referrer = _seeded_referrer(users_repo)
    referee = UserId.new()
    await referrals_repo.add(
        Referral.create_pending(referrer.id, referee, now)
    )
    service, referrals, _, subs = _make_service(
        referrals=referrals_repo, users=users_repo
    )

    await service.mark_profile_created(referee, now)
    assert subs.grants == []
    assert referrals.referrals[0].status.value == "pending"

    await service.mark_first_rating(referee, now)

    # Two BONUS grants, one for each party
    assert len(subs.grants) == 2
    owners = {g.owner_id for g in subs.grants}
    assert owners == {referrer.id, referee}
    assert all(g.source == GrantSource.BONUS for g in subs.grants)
    assert all(g.tier == Tier.BONUS for g in subs.grants)
    assert all(
        (g.expires_at - g.starts_at).days == REFERRAL_REWARD_DAYS
        for g in subs.grants
    )
    assert referrals.referrals[0].status.value == "rewarded"


async def test_banned_referrer_skipped_referee_still_rewarded() -> None:
    now = datetime.now(UTC)
    users_repo = FakeUserRepo()
    referrer = _seeded_referrer(users_repo)
    referrer.ban("spam", now=now)
    referee = UserId.new()
    referrals_repo = FakeReferralRepo()
    await referrals_repo.add(
        Referral.create_pending(referrer.id, referee, now)
    )
    service, _, _, subs = _make_service(
        referrals=referrals_repo, users=users_repo
    )

    await service.mark_profile_created(referee, now)
    await service.mark_first_rating(referee, now)

    # Referee gets their bonus; referrer does not.
    owners = {g.owner_id for g in subs.grants}
    assert owners == {referee}


async def test_repeated_calls_after_reward_are_noop() -> None:
    now = datetime.now(UTC)
    referrals_repo = FakeReferralRepo()
    users_repo = FakeUserRepo()
    referrer = _seeded_referrer(users_repo)
    referee = UserId.new()
    await referrals_repo.add(
        Referral.create_pending(referrer.id, referee, now)
    )
    service, _, _, subs = _make_service(
        referrals=referrals_repo, users=users_repo
    )

    await service.mark_profile_created(referee, now)
    await service.mark_first_rating(referee, now)
    assert len(subs.grants) == 2

    # Retries — should not re-grant.
    await service.mark_first_rating(referee, now)
    await service.mark_profile_created(referee, now)
    assert len(subs.grants) == 2

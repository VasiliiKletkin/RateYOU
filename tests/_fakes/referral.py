"""Tiny stand-ins for the Referral context, used by use case tests that don't
exercise the referral flow.

The use case under test gets a real `ReferralRewardService` wired with these
empty fakes — since no Referral row exists for the rater/owner, the service
returns immediately and never touches the user or subscription repos. This
keeps the test focused on the use case's own behavior without dragging the
referral context into every fixture.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.identity.entities import User
from src.domain.identity.value_objects import ReferralCode, TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.services import ReferralRewardService
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant


@dataclass
class EmptyReferralRepo:
    referrals: list[Referral] = field(default_factory=list)

    async def add(self, referral: Referral) -> None:
        self.referrals.append(referral)

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        for r in self.referrals:
            if r.referee_id == referee_id:
                return r
        return None

    async def list_by_referrer(self, referrer_id: UserId) -> list[Referral]:
        return [r for r in self.referrals if r.referrer_id == referrer_id]

    async def update(self, referral: Referral) -> None:
        for idx, existing in enumerate(self.referrals):
            if existing.id == referral.id:
                self.referrals[idx] = referral
                return


@dataclass
class EmptyUserRepo:
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
class EmptySubscriptionRepo:
    grants: list[SubscriptionGrant] = field(default_factory=list)

    async def add(self, grant: SubscriptionGrant) -> None:
        self.grants.append(grant)

    async def list_for(self, owner_id: UserId) -> list[SubscriptionGrant]:
        return []

    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[SubscriptionGrant]:
        return []

    async def find_by_transaction(self, transaction_id) -> SubscriptionGrant | None:  # type: ignore[no-untyped-def]
        return None

    async def update(self, grant: SubscriptionGrant) -> None:
        for idx, existing in enumerate(self.grants):
            if existing.id == grant.id:
                self.grants[idx] = grant
                return


def make_noop_referral_service() -> ReferralRewardService:
    """Real service wired with empty fakes. With no PENDING referral for any
    referee, every `mark_*` call short-circuits before touching subscriptions
    or users."""
    return ReferralRewardService(
        referral_repo=EmptyReferralRepo(),
        user_repo=EmptyUserRepo(),
        subscription_repo=EmptySubscriptionRepo(),
    )

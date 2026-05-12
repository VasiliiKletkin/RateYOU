from dataclasses import dataclass
from datetime import datetime

from src.domain.identity.repositories import IUserRepository
from src.domain.referral.entities import Referral
from src.domain.referral.repositories import IReferralRepository
from src.domain.referral.value_objects import ReferralStatus
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.repositories import ISubscriptionRepository

REFERRAL_REWARD_DAYS = 3


@dataclass
class ReferralRewardService:
    """Orchestrates referral progress flags and the reward grant flow.

    Both `mark_profile_created` and `mark_first_rating` are safe to call
    after every CreateProfile / RateUser invocation — they short-circuit
    when:
      - the referee has no PENDING referral (most users, who came in
        directly without a deep link)
      - the referral is already REWARDED (idempotent retries)
      - the flag is already set (e.g. re-rating after the first rating)

    When the second flag completes the pair, the aggregate transitions
    PENDING → QUALIFIED, and the service immediately issues BONUS
    SubscriptionGrants for both referrer and referee in the same UoW,
    finishing at REWARDED. A banned referrer at reward time is silently
    skipped; the referee still receives their grant.
    """

    referral_repo: IReferralRepository
    user_repo: IUserRepository
    subscription_repo: ISubscriptionRepository

    async def mark_profile_created(
        self, referee_id: UserId, now: datetime
    ) -> None:
        await self._mark(referee_id, now, flag="profile")

    async def mark_first_rating(
        self, referee_id: UserId, now: datetime
    ) -> None:
        await self._mark(referee_id, now, flag="rating")

    async def _mark(
        self,
        referee_id: UserId,
        now: datetime,
        flag: str,
    ) -> None:
        referral = await self.referral_repo.get_by_referee(referee_id)
        if referral is None or referral.status == ReferralStatus.REWARDED:
            return
        qualified_now = (
            referral.mark_profile_created(now)
            if flag == "profile"
            else referral.mark_first_rating(now)
        )
        if qualified_now:
            await self._grant_rewards(referral, now)
        await self.referral_repo.update(referral)

    async def _grant_rewards(
        self, referral: Referral, now: datetime
    ) -> None:
        # Referee did the work — they always get their bonus.
        await self.subscription_repo.add(
            SubscriptionGrant.create_bonus(
                owner_id=referral.referee_id,
                duration_days=REFERRAL_REWARD_DAYS,
                now=now,
            )
        )
        referrer = await self.user_repo.get_by_id(referral.referrer_id)
        if referrer is not None and not referrer.is_banned:
            await self.subscription_repo.add(
                SubscriptionGrant.create_bonus(
                    owner_id=referral.referrer_id,
                    duration_days=REFERRAL_REWARD_DAYS,
                    now=now,
                )
            )
        referral.mark_rewarded(now)

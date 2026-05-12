from dataclasses import dataclass
from datetime import datetime

from src.domain.identity.repositories import IUserRepository
from src.domain.referral.entities import Referral
from src.domain.referral.repositories import IReferralRepository
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionGrant
from src.domain.subscription.repositories import ISubscriptionRepository

# +1 day of premium per side per qualifying referral.
PER_REFERRAL_REWARD_DAYS = 1

# Every Nth completed referral gives the referrer an additional bonus on top
# of their per-referral day.
MILESTONE_INTERVAL = 3
MILESTONE_BONUS_DAYS = 3


@dataclass
class ReferralRewardService:
    """Pays out the referral reward when a referee creates their profile.

    Triggered by `CreateProfileUseCase`. A no-op for users without a
    referrer (`User.referred_by_user_id is None`). Idempotent: if a
    Referral row already exists for the referee, the call short-circuits
    so a profile re-creation flow couldn't double-pay.

    Reward semantics:
      - Both referrer and referee receive `PER_REFERRAL_REWARD_DAYS` as a
        BONUS SubscriptionGrant.
      - Once the referrer's running count hits a multiple of
        `MILESTONE_INTERVAL`, they get an additional `MILESTONE_BONUS_DAYS`
        on top — a second grant marking the milestone.
      - A banned referrer is silently skipped (referee still gets theirs).
    """

    referral_repo: IReferralRepository
    user_repo: IUserRepository
    subscription_repo: ISubscriptionRepository

    async def mark_profile_created(
        self, referee_id: UserId, now: datetime
    ) -> None:
        referee = await self.user_repo.get_by_id(referee_id)
        if referee is None or referee.referred_by_user_id is None:
            return
        if await self.referral_repo.exists_for_referee(referee_id):
            return  # Idempotent: already paid out.

        referrer_id = referee.referred_by_user_id
        referral = Referral.reward(referrer_id, referee_id, now)
        await self.referral_repo.add(referral)

        # Referee always receives their bonus — they did the work.
        await self.subscription_repo.add(
            SubscriptionGrant.create_bonus(
                owner_id=referee_id,
                duration_days=PER_REFERRAL_REWARD_DAYS,
                now=now,
            )
        )

        # Referrer: only paid if not banned at reward time.
        referrer = await self.user_repo.get_by_id(referrer_id)
        if referrer is None or referrer.is_banned:
            return
        await self.subscription_repo.add(
            SubscriptionGrant.create_bonus(
                owner_id=referrer_id,
                duration_days=PER_REFERRAL_REWARD_DAYS,
                now=now,
            )
        )

        # Milestone bonus: a second grant fires when the count crosses a
        # multiple of `MILESTONE_INTERVAL`.
        count = await self.referral_repo.count_for_referrer(referrer_id)
        if count > 0 and count % MILESTONE_INTERVAL == 0:
            await self.subscription_repo.add(
                SubscriptionGrant.create_bonus(
                    owner_id=referrer_id,
                    duration_days=MILESTONE_BONUS_DAYS,
                    now=now,
                )
            )

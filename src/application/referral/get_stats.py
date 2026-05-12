from dataclasses import dataclass
from uuid import UUID

from src.application.referral.dto import ReferralStatsResponse
from src.domain.identity.repositories import IUserRepository
from src.domain.referral.repositories import IReferralRepository
from src.domain.referral.services import MILESTONE_INTERVAL
from src.domain.shared.identifiers import UserId


@dataclass
class GetReferralStatsUseCase:
    """Counts the user's invitations + completed registrations + milestone gap.

    Invitations are users whose `referred_by_user_id` points at the
    requester (regardless of whether they finished their profile).
    Registrations are the rewarded subset (one Referral row per).
    """

    user_repo: IUserRepository
    referral_repo: IReferralRepository

    async def execute(self, owner_id: UUID) -> ReferralStatsResponse:
        owner = UserId(owner_id)
        invitations = await self.user_repo.count_referees_for(owner)
        registrations = await self.referral_repo.count_for_referrer(owner)
        # `next_milestone` rounds up to the next multiple of MILESTONE_INTERVAL.
        next_milestone_at = (
            (registrations // MILESTONE_INTERVAL) + 1
        ) * MILESTONE_INTERVAL
        return ReferralStatsResponse(
            invitations=invitations,
            registrations=registrations,
            referrals_until_next_milestone=next_milestone_at - registrations,
        )

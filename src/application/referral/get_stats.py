from dataclasses import dataclass
from uuid import UUID

from src.application.referral.dto import ReferralStatsResponse
from src.domain.referral.repositories import IReferralRepository
from src.domain.referral.services import MILESTONE_INTERVAL
from src.domain.shared.identifiers import UserId


@dataclass
class GetReferralStatsUseCase:
    """Counts the user's invitations + completed registrations + milestone gap.

    Invitations = total Referral rows where the requester is the referrer
    (both pending and rewarded — anyone who clicked the deep link).
    Registrations = the rewarded subset (referees who created their
    profile and triggered the bonus payout).
    """

    referral_repo: IReferralRepository

    async def execute(self, owner_id: UUID) -> ReferralStatsResponse:
        owner = UserId(owner_id)
        invitations = await self.referral_repo.count_total_for_referrer(owner)
        registrations = await self.referral_repo.count_rewarded_for_referrer(owner)
        # `next_milestone` rounds up to the next multiple of MILESTONE_INTERVAL.
        next_milestone_at = ((registrations // MILESTONE_INTERVAL) + 1) * MILESTONE_INTERVAL
        return ReferralStatsResponse(
            invitations=invitations,
            registrations=registrations,
            referrals_until_next_milestone=next_milestone_at - registrations,
        )

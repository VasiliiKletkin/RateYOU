from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReferralStatsResponse:
    """View model for the `/refer` command.

    invitations: how many users entered via this referrer's deep link
        (regardless of whether they completed their profile).
    registrations: how many of those went on to create a profile and
        trigger the bonus payout. Always `<= invitations`.
    referrals_until_next_milestone: how many more completed referrals are
        needed before the referrer hits the next milestone bonus.
    """

    invitations: int
    registrations: int
    referrals_until_next_milestone: int

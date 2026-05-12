class ReferralError(Exception):
    """Base for referral domain errors."""


class SelfReferral(ReferralError):
    """Raised when a user attempts to refer themselves."""


class InvalidReferralStatusTransition(ReferralError):
    """Raised when the FSM is driven through an illegal transition.

    Legal: PENDING -> QUALIFIED -> REWARDED. Everything else is rejected.
    """

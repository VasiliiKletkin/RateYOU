class ReferralError(Exception):
    """Base for referral domain errors."""


class SelfReferral(ReferralError):
    """Raised when a user attempts to refer themselves."""

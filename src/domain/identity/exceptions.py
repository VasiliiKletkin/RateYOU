class IdentityError(Exception):
    """Base for identity domain errors."""


class UserNotFound(IdentityError):
    pass


class UserAlreadyExists(IdentityError):
    pass


class UserIsBanned(IdentityError):
    pass


class InvalidBanReason(IdentityError):
    pass


class InvalidReferralCode(IdentityError):
    """Raised when a referral code string is malformed (wrong length or chars).

    Looking up a well-formed but unknown code is NOT this error — repositories
    return `None` instead.
    """

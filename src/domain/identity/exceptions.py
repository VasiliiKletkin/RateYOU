class IdentityError(Exception):
    """Base for identity domain errors."""


class UserNotFound(IdentityError):
    pass


class UserIsBanned(IdentityError):
    pass


class InvalidBanReason(IdentityError):
    pass

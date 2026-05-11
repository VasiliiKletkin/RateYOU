class SubscriptionError(Exception):
    """Base for subscription domain errors."""


class SubscriptionNotFound(SubscriptionError):
    pass


class InvalidTier(SubscriptionError):
    pass

class SubscriptionError(Exception):
    """Base for subscription domain errors."""


class SubscriptionNotFound(SubscriptionError):
    pass


class InvalidTier(SubscriptionError):
    pass


class PremiumRequired(SubscriptionError):
    """Raised when a premium-gated action is attempted without an active subscription."""

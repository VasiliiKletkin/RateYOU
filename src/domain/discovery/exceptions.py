class DiscoveryError(Exception):
    """Base for discovery (feed selection) errors."""


class InvalidMinRating(DiscoveryError):
    """Min-rating threshold is outside the [0, 10] range."""

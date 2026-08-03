class DiscoveryError(Exception):
    """Base for discovery (feed selection) errors."""


class InvalidMinRating(DiscoveryError):
    """Min-rating threshold is outside the [0, 10] range."""


class SearchLocationNotSet(DiscoveryError):
    """The viewer has no search location, so the feed has no origin to sort from.

    Raised by the feed use case instead of returning "no candidates" — the
    two are different outcomes: one is "set your city", the other is "come
    back later".
    """

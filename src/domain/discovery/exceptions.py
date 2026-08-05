class DiscoveryError(Exception):
    """Base for discovery (feed selection) errors."""


class InvalidMinRating(DiscoveryError):
    """Min-rating threshold is outside the [0, 10] range."""


class ProfileRequiredToContinue(DiscoveryError):
    """The viewer exhausted their free rating quota and has no profile.

    Browsing is open to everyone with a search location, but only up to
    `FREE_RATINGS_WITHOUT_PROFILE` ratings — the reciprocity gate that
    nudges lurkers into creating a profile of their own. The handler turns
    this into a "/create to keep rating" prompt.
    """


class SearchLocationNotSet(DiscoveryError):
    """The viewer has no search location, so the feed has no origin to sort from.

    Raised by the feed use case instead of returning "no candidates" — the
    two are different outcomes: one is "set your city", the other is "come
    back later".
    """

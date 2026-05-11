class RatingError(Exception):
    """Base for rating domain errors."""


class RatingNotFound(RatingError):
    pass


class InvalidScore(RatingError):
    pass


class CannotRateSelf(RatingError):
    pass

from dataclasses import dataclass

from src.domain.shared.identifiers import UserId
from src.domain.shared.specifications import Specification


@dataclass(frozen=True, slots=True)
class ProfileIsVisible(Specification):
    """Matches profiles that haven't been hidden by their owner."""


@dataclass(frozen=True, slots=True)
class ProfileNotOwnedBy(Specification):
    """Excludes the viewer's own profile from candidates."""

    user_id: UserId


@dataclass(frozen=True, slots=True)
class ProfileNotRatedBy(Specification):
    """Excludes profiles whose owner the rater has already scored."""

    rater_id: UserId


@dataclass(frozen=True, slots=True)
class ProfileAverageRatingAtLeast(Specification):
    """Premium filter: only profiles whose summary's avg_score >= threshold.

    Profiles with no ratings (no summary row) are excluded by this spec
    because the underlying JOIN is INNER.
    """

    threshold: float


@dataclass(frozen=True, slots=True)
class ProfileOwnerNotIn(Specification):
    """Excludes profiles owned by any user in the given list.

    Used to drop recently-skipped owners from the feed during their cooldown.
    `tuple` rather than `list` so the spec remains hashable / dataclass-frozen.
    """

    user_ids: tuple[UserId, ...]


def default_feed_spec(viewer_id: UserId) -> Specification:
    """Baseline composition: visible + not own + not already rated."""
    return (
        ProfileIsVisible()
        & ProfileNotOwnedBy(viewer_id)
        & ProfileNotRatedBy(viewer_id)
    )

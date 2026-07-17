from typing import Any

from sqlalchemy import Select, not_, select

from src.domain.discovery.specifications import (
    ProfileAverageRatingAtLeast,
    ProfileHasGender,
    ProfileIsVisible,
    ProfileNotOwnedBy,
    ProfileNotRatedBy,
    ProfileOwnerNotIn,
)
from src.domain.shared.specifications import AndSpec, Specification
from src.infrastructure.db.models.profile import ProfileORM
from src.infrastructure.db.models.rating import ProfileScoreSummaryORM, RatingORM


class DiscoverySpecApplier:
    """Visitor that turns a Specification into WHERE / JOIN clauses.

    Concentrates the SQL knowledge in one place; the repository just builds
    the base SELECT and lets the applier finish the WHERE.
    """

    def apply[T: tuple[Any, ...]](
        self,
        stmt: Select[T],
        spec: Specification,
    ) -> Select[T]:
        if isinstance(spec, AndSpec):
            for inner in spec.specs:
                stmt = self.apply(stmt, inner)
            return stmt
        if isinstance(spec, ProfileIsVisible):
            return stmt.where(ProfileORM.is_visible.is_(True))
        if isinstance(spec, ProfileNotOwnedBy):
            return stmt.where(ProfileORM.owner_id != spec.user_id.value)
        if isinstance(spec, ProfileHasGender):
            return stmt.where(ProfileORM.gender == spec.gender.value)
        if isinstance(spec, ProfileNotRatedBy):
            already_rated = (
                select(RatingORM.id)
                .where(
                    RatingORM.rater_id == spec.rater_id.value,
                    RatingORM.rated_id == ProfileORM.owner_id,
                )
                .exists()
            )
            return stmt.where(not_(already_rated))
        if isinstance(spec, ProfileAverageRatingAtLeast):
            return stmt.join(
                ProfileScoreSummaryORM,
                ProfileScoreSummaryORM.rated_id == ProfileORM.owner_id,
            ).where(ProfileScoreSummaryORM.average_score >= spec.threshold)
        if isinstance(spec, ProfileOwnerNotIn):
            if not spec.user_ids:
                return stmt
            return stmt.where(ProfileORM.owner_id.not_in([uid.value for uid in spec.user_ids]))
        raise ValueError(f"Unknown specification: {type(spec).__name__}")

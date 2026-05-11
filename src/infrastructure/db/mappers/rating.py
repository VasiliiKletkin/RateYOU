from src.domain.rating.entities import Rating
from src.domain.rating.read_models import ProfileScoreSummary
from src.domain.rating.value_objects import RatingId, Score
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.rating import ProfileScoreSummaryORM, RatingORM


def rating_to_orm(rating: Rating) -> RatingORM:
    return RatingORM(
        id=rating.id.value,
        rater_id=rating.rater_id.value,
        rated_id=rating.rated_id.value,
        score=rating.score.value,
        created_at=rating.created_at,
        updated_at=rating.updated_at,
    )


def orm_to_rating(orm: RatingORM) -> Rating:
    return Rating(
        id=RatingId(orm.id),
        rater_id=UserId(orm.rater_id),
        rated_id=UserId(orm.rated_id),
        score=Score(orm.score),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def summary_to_orm(summary: ProfileScoreSummary) -> ProfileScoreSummaryORM:
    return ProfileScoreSummaryORM(
        rated_id=summary.rated_id.value,
        average_score=summary.average_score,
        rating_count=summary.rating_count,
        updated_at=summary.updated_at,
    )


def orm_to_summary(orm: ProfileScoreSummaryORM) -> ProfileScoreSummary:
    return ProfileScoreSummary(
        rated_id=UserId(orm.rated_id),
        average_score=orm.average_score,
        rating_count=orm.rating_count,
        updated_at=orm.updated_at,
    )

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.rating.entities import Rating
from src.domain.rating.value_objects import Score
from src.infrastructure.db.repositories.rating import RatingRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user_repo = UserRepository(session=session)
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await user_repo.add(user)
    return user


async def test_add_and_get_by_rater_and_rated(session: AsyncSession) -> None:
    rater = await _seed_user(session, 2001)
    rated = await _seed_user(session, 2002)
    repo = RatingRepository(session=session)
    now = datetime.now(UTC)
    rating = Rating.give(rater.id, rated.id, Score(8), now)

    await repo.add(rating)

    found = await repo.get_by_rater_and_rated(rater.id, rated.id)
    assert found is not None
    assert found.score == Score(8)
    assert found.rater_id == rater.id
    assert found.rated_id == rated.id


async def test_compute_stats_with_no_ratings(session: AsyncSession) -> None:
    rated = await _seed_user(session, 2003)
    repo = RatingRepository(session=session)

    avg, count = await repo.compute_stats_for(rated.id)

    assert avg == 0.0
    assert count == 0


async def test_compute_stats_averages_multiple_raters(session: AsyncSession) -> None:
    rated = await _seed_user(session, 2010)
    rater_a = await _seed_user(session, 2011)
    rater_b = await _seed_user(session, 2012)
    rater_c = await _seed_user(session, 2013)
    repo = RatingRepository(session=session)
    now = datetime.now(UTC)

    await repo.add(Rating.give(rater_a.id, rated.id, Score(4), now))
    await repo.add(Rating.give(rater_b.id, rated.id, Score(7), now))
    await repo.add(Rating.give(rater_c.id, rated.id, Score(10), now))

    avg, count = await repo.compute_stats_for(rated.id)
    assert avg == 7.0  # (4+7+10)/3
    assert count == 3


async def test_update_changes_score(session: AsyncSession) -> None:
    rater = await _seed_user(session, 2020)
    rated = await _seed_user(session, 2021)
    repo = RatingRepository(session=session)
    now = datetime.now(UTC)
    rating = Rating.give(rater.id, rated.id, Score(5), now)
    await repo.add(rating)

    rating.change_score(Score(9), now=now)
    await repo.update(rating)

    refreshed = await repo.get_by_rater_and_rated(rater.id, rated.id)
    assert refreshed is not None
    assert refreshed.score == Score(9)


async def test_delete_removes_rating(session: AsyncSession) -> None:
    rater = await _seed_user(session, 2030)
    rated = await _seed_user(session, 2031)
    repo = RatingRepository(session=session)
    rating = Rating.give(rater.id, rated.id, Score(6), datetime.now(UTC))
    await repo.add(rating)

    await repo.delete(rating)

    assert await repo.get_by_rater_and_rated(rater.id, rated.id) is None


async def test_list_for_rated_returns_newest_first_capped_by_limit(
    session: AsyncSession,
) -> None:
    rated = await _seed_user(session, 2040)
    rater_a = await _seed_user(session, 2041)
    rater_b = await _seed_user(session, 2042)
    rater_c = await _seed_user(session, 2043)
    repo = RatingRepository(session=session)
    base = datetime.now(UTC)

    # Distinct created_at values so ORDER BY is deterministic.
    await repo.add(
        Rating(
            id=Rating.give(rater_a.id, rated.id, Score(4), base).id,
            rater_id=rater_a.id,
            rated_id=rated.id,
            score=Score(4),
            created_at=base - timedelta(hours=2),
            updated_at=base - timedelta(hours=2),
        )
    )
    await repo.add(
        Rating(
            id=Rating.give(rater_b.id, rated.id, Score(7), base).id,
            rater_id=rater_b.id,
            rated_id=rated.id,
            score=Score(7),
            created_at=base - timedelta(minutes=30),
            updated_at=base - timedelta(minutes=30),
        )
    )
    await repo.add(
        Rating(
            id=Rating.give(rater_c.id, rated.id, Score(9), base).id,
            rater_id=rater_c.id,
            rated_id=rated.id,
            score=Score(9),
            created_at=base,
            updated_at=base,
        )
    )

    all_three = await repo.list_for_rated(rated.id, limit=10)
    assert [r.score.value for r in all_three] == [9, 7, 4]

    top_two = await repo.list_for_rated(rated.id, limit=2)
    assert [r.score.value for r in top_two] == [9, 7]


async def test_list_for_rated_returns_empty_when_no_ratings(
    session: AsyncSession,
) -> None:
    rated = await _seed_user(session, 2050)
    repo = RatingRepository(session=session)

    assert await repo.list_for_rated(rated.id, limit=10) == []

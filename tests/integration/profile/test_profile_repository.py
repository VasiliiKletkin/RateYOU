from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    PhotoFileId,
    Photos,
)
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user_repo = UserRepository(session=session)
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await user_repo.add(user)
    return user


def _make_profile(owner_id: object) -> Profile:
    now = datetime.now(UTC)
    return Profile.create(
        owner_id=owner_id,  # type: ignore[arg-type]
        name=Name("Vasya"),
        age=Age(25),
        gender=Gender.MALE,
        bio=Bio("hi"),
        photos=Photos(items=(PhotoFileId("file-id-1"),)),
        location=Location(lat=55.7558, lon=37.6173),
        now=now,
    )


async def test_add_and_get_by_owner_id_roundtrip(session: AsyncSession) -> None:
    user = await _seed_user(session, 1001)
    repo = ProfileRepository(session=session)
    profile = _make_profile(user.id)

    await repo.add(profile)

    found = await repo.get_by_owner_id(user.id)
    assert found is not None
    assert found.id == profile.id
    assert found.name == Name("Vasya")
    assert found.age == Age(25)
    assert found.gender == Gender.MALE
    assert found.is_visible is True


async def test_get_by_id_roundtrip(session: AsyncSession) -> None:
    user = await _seed_user(session, 1002)
    repo = ProfileRepository(session=session)
    profile = _make_profile(user.id)
    await repo.add(profile)

    found = await repo.get_by_id(profile.id)
    assert found is not None
    assert found.owner_id == user.id


async def test_exists_for_owner(session: AsyncSession) -> None:
    user = await _seed_user(session, 1003)
    repo = ProfileRepository(session=session)

    assert await repo.exists_for_owner(user.id) is False

    await repo.add(_make_profile(user.id))

    assert await repo.exists_for_owner(user.id) is True


async def test_update_persists_changes(session: AsyncSession) -> None:
    user = await _seed_user(session, 1004)
    repo = ProfileRepository(session=session)
    profile = _make_profile(user.id)
    await repo.add(profile)

    now = datetime.now(UTC)
    profile.update_bio(Bio("updated bio"), now=now)
    profile.hide(now=now)
    await repo.update(profile)

    refreshed = await repo.get_by_id(profile.id)
    assert refreshed is not None
    assert refreshed.bio == Bio("updated bio")
    assert refreshed.is_visible is False


async def test_photos_reconcile_replaces_set(session: AsyncSession) -> None:
    user = await _seed_user(session, 1005)
    repo = ProfileRepository(session=session)
    profile = _make_profile(user.id)
    await repo.add(profile)

    new_photos = Photos(
        items=(
            PhotoFileId("file-id-a"),
            PhotoFileId("file-id-b"),
            PhotoFileId("file-id-c"),
        )
    )
    profile.update_photos(new_photos, now=datetime.now(UTC))
    await repo.update(profile)

    refreshed = await repo.get_by_id(profile.id)
    assert refreshed is not None
    assert refreshed.photos == new_photos
    assert refreshed.photos.to_strings() == ["file-id-a", "file-id-b", "file-id-c"]

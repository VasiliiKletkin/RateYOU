from datetime import UTC, datetime, timedelta

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
from src.domain.shared.identifiers import UserId


def _make_profile(now: datetime) -> Profile:
    return Profile.create(
        owner_id=UserId.new(),
        name=Name("Vasya"),
        age=Age(25),
        gender=Gender.MALE,
        bio=Bio("hi"),
        photos=Photos(items=(PhotoFileId("file-id-1"),)),
        location=Location(lat=55.7558, lon=37.6173),
        now=now,
    )


def test_create_sets_initial_state() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)

    assert p.name == Name("Vasya")
    assert p.age == Age(25)
    assert p.gender == Gender.MALE
    assert p.is_visible is True
    assert p.created_at == now
    assert p.updated_at == now


def test_update_bio_changes_bio_and_updated_at() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)
    later = now + timedelta(minutes=1)

    p.update_bio(Bio("new bio"), now=later)

    assert p.bio == Bio("new bio")
    assert p.updated_at == later
    assert p.created_at == now  # unchanged


def test_update_photos_changes_photos() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)
    later = now + timedelta(minutes=1)
    new_photos = Photos(
        items=(PhotoFileId("file-id-2"), PhotoFileId("file-id-3"))
    )

    p.update_photos(new_photos, now=later)

    assert p.photos == new_photos
    assert len(p.photos) == 2
    assert p.updated_at == later


def test_update_basics_partial_keeps_other_fields() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)
    later = now + timedelta(minutes=1)

    p.update_basics(name=Name("Petya"), age=None, gender=None, now=later)

    assert p.name == Name("Petya")
    assert p.age == Age(25)  # unchanged
    assert p.gender == Gender.MALE  # unchanged
    assert p.updated_at == later


def test_hide_marks_invisible() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)

    p.hide(now=now)

    assert p.is_visible is False


def test_show_marks_visible() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)
    p.hide(now=now)

    p.show(now=now)

    assert p.is_visible is True


def test_create_sets_location() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)

    assert p.location == Location(lat=55.7558, lon=37.6173)


def test_update_location_changes_location_and_updated_at() -> None:
    now = datetime.now(UTC)
    p = _make_profile(now)
    later = now + timedelta(minutes=1)
    loc = Location(lat=10.0, lon=20.0)

    p.update_location(loc, now=later)

    assert p.location == loc
    assert p.updated_at == later
    assert p.created_at == now

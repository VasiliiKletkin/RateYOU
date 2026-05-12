import pytest

from src.domain.profile.exceptions import (
    InvalidAge,
    InvalidLocation,
    InvalidName,
    InvalidPhoto,
    InvalidPhotos,
)
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    PhotoFileId,
    Photos,
)


class TestName:
    def test_strips_whitespace(self) -> None:
        assert Name("  Vasya  ").value == "Vasya"

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidName):
            Name("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(InvalidName):
            Name("   ")

class TestAge:
    def test_accepts_in_range(self) -> None:
        assert Age(18).value == 18
        assert Age(50).value == 50
        assert Age(100).value == 100

    def test_rejects_below_min(self) -> None:
        with pytest.raises(InvalidAge):
            Age(17)

    def test_rejects_above_max(self) -> None:
        with pytest.raises(InvalidAge):
            Age(101)


class TestGender:
    def test_accepts_male(self) -> None:
        assert Gender("male") == Gender.MALE

    def test_accepts_female(self) -> None:
        assert Gender("female") == Gender.FEMALE

    def test_rejects_unknown(self) -> None:
        with pytest.raises(ValueError):
            Gender("other")


class TestBio:
    def test_accepts_empty(self) -> None:
        assert Bio("").value == ""

    def test_accepts_normal(self) -> None:
        assert Bio("hello world").value == "hello world"

class TestPhotoFileId:
    def test_accepts_telegram_file_id(self) -> None:
        fid = "AgACAgIAAxkBAAEBxxxxxxxxxxxxxxxxxxxx"
        assert PhotoFileId(fid).value == fid

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidPhoto):
            PhotoFileId("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(InvalidPhoto):
            PhotoFileId("   ")


class TestPhotos:
    def test_accepts_single_photo(self) -> None:
        photos = Photos(items=(PhotoFileId("file-1"),))
        assert len(photos) == 1
        assert photos.first.value == "file-1"

    def test_accepts_max_photos(self) -> None:
        ids = tuple(PhotoFileId(f"f{i}") for i in range(6))
        photos = Photos(items=ids)
        assert len(photos) == 6

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidPhotos):
            Photos(items=())

    def test_rejects_over_max(self) -> None:
        ids = tuple(PhotoFileId(f"f{i}") for i in range(7))
        with pytest.raises(InvalidPhotos):
            Photos(items=ids)

    def test_from_strings(self) -> None:
        photos = Photos.from_strings(["a", "b", "c"])
        assert photos.to_strings() == ["a", "b", "c"]

    def test_to_strings_preserves_order(self) -> None:
        photos = Photos.from_strings(["x", "y"])
        assert photos.to_strings() == ["x", "y"]


class TestLocation:
    def test_accepts_valid(self) -> None:
        loc = Location(lat=55.7558, lon=37.6173)
        assert loc.lat == 55.7558
        assert loc.lon == 37.6173

    def test_accepts_origin(self) -> None:
        assert Location(lat=0.0, lon=0.0).lat == 0.0

    def test_accepts_boundaries(self) -> None:
        Location(lat=90.0, lon=180.0)
        Location(lat=-90.0, lon=-180.0)

    def test_rejects_lat_above_90(self) -> None:
        with pytest.raises(InvalidLocation):
            Location(lat=90.0001, lon=0.0)

    def test_rejects_lat_below_minus_90(self) -> None:
        with pytest.raises(InvalidLocation):
            Location(lat=-90.0001, lon=0.0)

    def test_rejects_lon_above_180(self) -> None:
        with pytest.raises(InvalidLocation):
            Location(lat=0.0, lon=180.0001)

    def test_rejects_lon_below_minus_180(self) -> None:
        with pytest.raises(InvalidLocation):
            Location(lat=0.0, lon=-180.0001)

    def test_is_immutable(self) -> None:
        loc = Location(lat=1.0, lon=2.0)
        with pytest.raises(AttributeError):
            loc.lat = 5.0  # type: ignore[misc]

from uuid import UUID, uuid4

from geoalchemy2 import WKBElement, WKTElement
from geoalchemy2.shape import to_shape

from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    PhotoFileId,
    Photos,
    ProfileId,
)
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.profile import ProfileORM, ProfilePhotoORM


def _location_to_wkt(loc: Location) -> WKTElement:
    # PostGIS POINT order is (lon, lat) — (x, y) in cartesian terms.
    return WKTElement(f"POINT({loc.lon} {loc.lat})", srid=4326)


def _wkb_to_location(wkb: WKBElement) -> Location:
    point = to_shape(wkb)  # shapely.Point; .x = lon, .y = lat
    return Location(lat=float(point.y), lon=float(point.x))


def _photos_to_orm(profile_id: UUID, photos: Photos) -> list[ProfilePhotoORM]:
    return [
        ProfilePhotoORM(
            id=uuid4(),
            profile_id=profile_id,
            file_id=photo.value,
            position=idx,
        )
        for idx, photo in enumerate(photos.items)
    ]


def _orm_to_photos(orm_photos: list[ProfilePhotoORM]) -> Photos:
    # Defensive sort — relationship already orders by position, but a stale
    # session or a hand-built list might not. Cheap insurance.
    sorted_photos = sorted(orm_photos, key=lambda p: p.position)
    return Photos(items=tuple(PhotoFileId(p.file_id) for p in sorted_photos))


def profile_to_orm(profile: Profile) -> ProfileORM:
    orm = ProfileORM(
        id=profile.id.value,
        owner_id=profile.owner_id.value,
        name=profile.name.value,
        age=profile.age.value,
        gender=profile.gender.value,
        bio=profile.bio.value,
        is_visible=profile.is_visible,
        location=_location_to_wkt(profile.location),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
    orm.photos = _photos_to_orm(profile.id.value, profile.photos)
    return orm


def orm_to_profile(orm: ProfileORM) -> Profile:
    return Profile(
        id=ProfileId(orm.id),
        owner_id=UserId(orm.owner_id),
        name=Name(orm.name),
        age=Age(orm.age),
        gender=Gender(orm.gender),
        bio=Bio(orm.bio),
        photos=_orm_to_photos(orm.photos),
        location=_wkb_to_location(orm.location),
        is_visible=orm.is_visible,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )

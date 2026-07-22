from dataclasses import dataclass

from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_Distance
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.discovery.repositories import DiscoveryMatch
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Location,
    Name,
    PhotoFileId,
    Photos,
    ProfileId,
)
from src.domain.shared.identifiers import UserId
from src.domain.shared.specifications import Specification
from src.infrastructure.db.discovery_spec_applier import DiscoverySpecApplier
from src.infrastructure.db.geo import wkb_to_location
from src.infrastructure.db.models.profile import ProfileORM


@dataclass
class DiscoveryRepository:
    """Compiles the given Specification to SQL via `DiscoverySpecApplier`.

    All cross-context query knowledge (joining `profile_score_summaries`,
    NOT EXISTS on ratings, etc.) lives in the applier; this class handles
    ordering by distance + projecting it into the result.
    """

    session: AsyncSession

    async def find_next(
        self,
        spec: Specification,
        viewer_location: Location,
    ) -> DiscoveryMatch | None:
        # PostGIS POINT is (lon, lat). ST_Distance on geography returns
        # meters along the WGS84 ellipsoid.
        viewer_point = WKTElement(
            f"POINT({viewer_location.lon} {viewer_location.lat})",
            srid=4326,
        )
        distance_expr = ST_Distance(ProfileORM.location, viewer_point)

        stmt: Select[tuple[ProfileORM, float]] = (
            select(ProfileORM, distance_expr.label("distance"))
            # `lazy="selectin"` on the relationship is unreliable when the
            # outer SELECT mixes the entity with extra columns — make the
            # photo load explicit so the feed always shows the full set.
            .options(selectinload(ProfileORM.photos))
        )
        stmt = DiscoverySpecApplier().apply(stmt, spec)
        stmt = stmt.order_by(distance_expr.asc()).limit(1)

        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        orm, distance = row
        return DiscoveryMatch(
            profile=Profile(
                id=ProfileId(orm.id),
                owner_id=UserId(orm.owner_id),
                name=Name(orm.name),
                age=Age(orm.age),
                gender=orm.gender,
                bio=Bio(orm.bio),
                photos=Photos(
                    items=tuple(
                        PhotoFileId(p.file_id) for p in sorted(orm.photos, key=lambda p: p.position)
                    )
                ),
                location=wkb_to_location(orm.location),
                is_visible=orm.is_visible,
                created_at=orm.created_at,
                updated_at=orm.updated_at,
            ),
            distance_meters=int(distance),
        )

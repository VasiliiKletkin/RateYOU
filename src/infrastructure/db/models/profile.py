from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geography, WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.profile.value_objects import Gender
from src.infrastructure.db.models.base import Base, str_enum


class ProfileORM(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int]
    gender: Mapped[Gender] = mapped_column(str_enum(Gender, "gender"))
    bio: Mapped[str] = mapped_column(String(500), server_default="")
    is_visible: Mapped[bool] = mapped_column(server_default="true")
    # PostGIS geography (Point, SRID 4326). NOT NULL — every profile must
    # have a location. GiST index lives in a migration.
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 1..6 photos in domain order. Loaded eagerly with `selectin` so a single
    # query brings every photo with its profile; cascade keeps `profile_photos`
    # in sync when the profile row is dropped.
    photos: Mapped[list["ProfilePhotoORM"]] = relationship(
        "ProfilePhotoORM",
        order_by="ProfilePhotoORM.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def location_display(self) -> str:
        """Human-readable 'lat, lon' for the admin panel.

        Starlette-Admin has no converter for PostGIS WKBElement, so we expose
        a derived string and reference it from the admin instead of the raw
        column.
        """
        pt = to_shape(self.location)
        return f"{pt.y:.6f}, {pt.x:.6f}"

    @property
    def photos_display(self) -> str:
        """Compact count for the admin list view."""
        if not self.photos:
            return "—"
        return f"{len(self.photos)} photo(s)"

    @property
    def photos_detail(self) -> str:
        """Full file_id list with positions for the admin detail view."""
        if not self.photos:
            return "—"
        return "\n".join(
            f"[{p.position}] {p.file_id}"
            for p in sorted(self.photos, key=lambda x: x.position)
        )


class ProfilePhotoORM(Base):
    __tablename__ = "profile_photos"
    __table_args__ = (
        UniqueConstraint("profile_id", "position", name="uq_profile_photos_position"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(String(500))
    # 0-based position. Reconciler in `ProfileRepository.update` rewrites
    # positions on every save so insertion/removal in the middle is cheap.
    position: Mapped[int]

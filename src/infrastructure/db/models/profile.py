from uuid import UUID, uuid4

from geoalchemy2 import Geography, WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.profile.value_objects import Gender
from src.infrastructure.db.models.base import Base, CreatedAtMixin, UpdatedAtMixin


class ProfileORM(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int]
    gender: Mapped[Gender] = mapped_column(Enum(Gender))
    bio: Mapped[str] = mapped_column(String(500), default="")
    is_visible: Mapped[bool] = mapped_column(default=True)
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
    )

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
    position: Mapped[int]

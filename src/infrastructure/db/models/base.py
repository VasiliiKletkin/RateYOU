from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ORM models live separately from domain entities (see
    infrastructure/db/mappers/ for the translation layer).
    """


class CreatedAtMixin:
    """Adds an immutable `created_at` column populated by the DB.

    Use as a second base class: ``class SomeORM(Base, CreatedAtMixin)``.
    Default fires for any INSERT path (ORM, admin form, raw SQL) because
    it's a server-side `now()` baked into the DDL.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdatedAtMixin:
    """Adds an auto-touching `updated_at` column.

    `server_default` fills the row on INSERT; `onupdate` makes SA append
    `updated_at = now()` to every UPDATE statement automatically. Manual
    assignments (e.g. from a domain entity's `now` injection) take
    precedence — `onupdate` only fires when the column isn't set
    explicitly.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

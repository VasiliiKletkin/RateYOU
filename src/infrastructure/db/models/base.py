from enum import StrEnum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


def str_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """Postgres ENUM that stores the StrEnum's .value (not its .name).

    SA's default ``Enum(EnumClass)`` stores ``EnumClass.MEMBER.name`` (e.g.
    "BRONZE"). Our domain enums use lower-case business values, so
    ``values_callable`` is overridden to keep DB and code aligned. The
    column round-trips as the enum instance — mappers pass ``entity.field``
    directly, no ``.value`` or cast.
    """
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda c: [e.value for e in c],
    )


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ORM models live separately from domain entities (see
    infrastructure/db/mappers/ for the translation layer).
    """

from enum import StrEnum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ORM models live separately from domain entities (see infrastructure/db/mappers/
    for the translation layer).
    """


def str_enum_column(
    enum_class: type[StrEnum], name: str
) -> Enum:
    """SQLAlchemy column type backed by a Postgres ENUM that stores the
    StrEnum's `.value`, not its member name.

    SA's default `Enum(EnumClass)` stores `EnumClass.MEMBER.name` (e.g.
    "BRONZE"). Our domain enums use lower-case business values
    ("bronze"), so we override `values_callable` to keep DB and code
    aligned. The column round-trips as an enum instance, which means
    mappers can pass `entity.field` directly — no `.value` or cast.
    """
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda c: [e.value for e in c],
    )

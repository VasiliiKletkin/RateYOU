from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ORM models live separately from domain entities (see infrastructure/db/mappers/
    for the translation layer).
    """

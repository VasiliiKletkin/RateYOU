from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.models.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), server_default="user")
    is_banned: Mapped[bool] = mapped_column(server_default="false")
    ban_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Short ISO 639-1 code. Server default lets the column be added in-place
    # without a backfill; existing users get "en" until they next /start.
    language: Mapped[str] = mapped_column(String(8), server_default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.models.base import Base


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

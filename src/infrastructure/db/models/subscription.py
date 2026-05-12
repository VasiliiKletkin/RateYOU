from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.models.base import Base
from src.infrastructure.db.models.identity import UserORM


class SubscriptionORM(Base):
    __tablename__ = "subscriptions"

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Exposed to Starlette-Admin so create/edit forms get a user dropdown;
    # the SQLA converter skips PK columns from create forms, leaving owner_id
    # unset and the INSERT failing NOT NULL. Assigning `owner` propagates the
    # FK on flush.
    owner: Mapped[UserORM] = relationship(UserORM)
    tier: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_revoked: Mapped[bool] = mapped_column(server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

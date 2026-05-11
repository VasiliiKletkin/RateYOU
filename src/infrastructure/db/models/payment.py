from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.models.base import Base


class TransactionORM(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(8))
    provider: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

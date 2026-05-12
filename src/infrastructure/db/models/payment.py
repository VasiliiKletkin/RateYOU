from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.payment.value_objects import Provider, Status
from src.infrastructure.db.models.base import Base, str_enum_column


class TransactionORM(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(8))
    provider: Mapped[Provider] = mapped_column(
        str_enum_column(Provider, name="payment_provider")
    )
    purpose: Mapped[str] = mapped_column(String(100))
    status: Mapped[Status] = mapped_column(
        str_enum_column(Status, name="payment_status")
    )
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

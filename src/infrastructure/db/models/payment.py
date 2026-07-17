from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.payment.value_objects import Provider, Status
from src.infrastructure.db.models.base import Base, CreatedAtMixin, UpdatedAtMixin


class TransactionORM(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(8))
    provider: Mapped[Provider] = mapped_column(Enum(Provider))
    purpose: Mapped[str] = mapped_column(String(64))
    status: Mapped[Status] = mapped_column(Enum(Status))
    external_id: Mapped[str | None] = mapped_column(String(128), default=None)

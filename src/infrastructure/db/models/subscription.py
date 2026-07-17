from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.subscription.value_objects import SubscriptionSource, Tier
from src.infrastructure.db.models.base import Base, CreatedAtMixin
from src.infrastructure.db.models.identity import UserORM
from src.infrastructure.db.models.payment import TransactionORM


class SubscriptionORM(Base, CreatedAtMixin):
    """One row per granted period of premium days (purchase, bonus, ...).

    The user's current premium state is derived from the set of their grants
    (filtered by `is_revoked=False` and `expires_at > now`). There is no
    UNIQUE on `owner_id` — a user typically has many grants over time and
    may have multiple active ones (e.g. a paid PURCHASE plus a BONUS).

    `transaction_id` links a PURCHASE grant to the paying Transaction so
    refunds can revoke exactly that grant without touching others.
    """

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner: Mapped[UserORM] = relationship(UserORM)
    tier: Mapped[Tier] = mapped_column(Enum(Tier), nullable=False)
    source: Mapped[SubscriptionSource] = mapped_column(Enum(SubscriptionSource), nullable=False)
    transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    transaction: Mapped[TransactionORM | None] = relationship(TransactionORM)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        Index(
            "ix_subscriptions_owner_expires",
            "owner_id",
            "expires_at",
        ),
        Index(
            "ix_subscriptions_transaction",
            "transaction_id",
            unique=True,
            postgresql_where="transaction_id IS NOT NULL",
        ),
    )

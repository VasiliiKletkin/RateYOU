from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.models.base import Base, CreatedAtMixin
from src.infrastructure.db.models.identity import UserORM


class ReferralORM(Base, CreatedAtMixin):
    """One row per paid-out referral.

    `referee_id` is UNIQUE — a user can only be referred once, regardless
    of how many `/start <telegram_id>` payloads target them. There is no
    status column: row existence == reward already issued.
    """

    __tablename__ = "referrals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    referrer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    referrer: Mapped[UserORM] = relationship(
        UserORM, foreign_keys=[referrer_id]
    )
    referee: Mapped[UserORM] = relationship(UserORM, foreign_keys=[referee_id])

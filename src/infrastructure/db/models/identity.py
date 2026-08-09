from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.identity.value_objects import Language, Role
from src.infrastructure.db.models.base import Base, CreatedAtMixin


class UserORM(Base, CreatedAtMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # Telegram caps handles at 32 chars. Nullable: many accounts have none.
    username: Mapped[str | None] = mapped_column(String(32), default=None)
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER)
    is_banned: Mapped[bool] = mapped_column(default=False)
    ban_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.EN)


class AcquisitionSourceORM(Base, CreatedAtMixin):
    """Dictionary of acquisition sources: marketing channels AND referrers.

    A source is *where a user came from*, in either shape:
      - a campaign tag (`?start=habr`) → `referrer_id IS NULL`, code is the
        lowercase tag; auto-created on first arrival or pre-created via the
        admin before a campaign starts;
      - a person who shared their `/refer` link (`?start=<telegram_id>`) →
        `referrer_id` points at that user, code is their telegram_id as a
        string (exactly what the deep link carries).

    The shapes can't collide on `code`: numeric payloads are always parsed
    as referrers, so a campaign tag is never purely numeric.
    """

    __tablename__ = "acquisition_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Set → this source IS a person. CASCADE: deleting the person deletes
    # their personal source row (and, via acquisitions.source_id CASCADE,
    # the attribution links of the people they invited — not those users).
    referrer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        default=None,
        index=True,
    )
    referrer: Mapped[UserORM | None] = relationship(UserORM)


class AcquisitionORM(Base, CreatedAtMixin):
    """One row per user: which source brought them in.

    `user_id` is the primary key — a user is acquired exactly once, and the
    row is never rewritten, so a later click on someone's referral link
    can't overwrite the original attribution.

    `rewarded_at` is the referral-reward lifecycle and is meaningful only
    when the source is a person (`source.referrer_id IS NOT NULL`): NULL =
    pending, set = both sides received their premium bonus. For campaign
    sources it stays NULL forever.
    """

    __tablename__ = "acquisitions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Indexed because every funnel report groups by source.
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_sources.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[AcquisitionSourceORM] = relationship(AcquisitionSourceORM)
    rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.identity.value_objects import Language, Role
from src.infrastructure.db.models.base import Base, CreatedAtMixin


class UserORM(Base, CreatedAtMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # Telegram caps handles at 32 chars. Nullable: many accounts have none.
    username: Mapped[str | None] = mapped_column(String(32), default=None)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.USER)
    is_banned: Mapped[bool] = mapped_column(default=False)
    ban_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.EN)

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from src.domain.payment.exceptions import InvalidMoney


@dataclass(frozen=True, slots=True)
class TransactionId:
    value: UUID

    @classmethod
    def new(cls) -> "TransactionId":
        return cls(uuid4())


class Provider(StrEnum):
    TELEGRAM_STARS = "telegram_stars"
    # Future: YOOKASSA = "yookassa", STRIPE = "stripe"


class Status(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class Money:
    """Amount in the smallest unit of `currency`.

    For Telegram Stars (`XTR`), one star = amount of 1. For RUB, amount is in
    kopecks. For USD/EUR, amount is in cents.
    """

    amount: int
    currency: str  # ISO 4217 + "XTR" for Telegram Stars

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise InvalidMoney(f"Amount must be positive, got {self.amount}")
        if not self.currency or len(self.currency) > 8:
            raise InvalidMoney(f"Invalid currency code: {self.currency!r}")

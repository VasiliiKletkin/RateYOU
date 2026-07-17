from dataclasses import dataclass, field
from datetime import datetime

from src.domain.payment.events import PaymentConfirmed, PaymentRefunded
from src.domain.payment.exceptions import InvalidStatusTransition
from src.domain.payment.value_objects import (
    Money,
    Provider,
    Status,
    TransactionId,
)
from src.domain.shared.events import DomainEvent
from src.domain.shared.identifiers import UserId


@dataclass
class Transaction:
    """Aggregate root: a single payment lifecycle from invoice to refund.

    State machine:
        PENDING ─► PAID ─► REFUNDED
                └► FAILED

    Provider-agnostic — no Telegram-specific fields. The `TelegramStarsGateway`
    infrastructure adapter resolves `payer_id` → `User.telegram_id` via the
    Identity context when it needs to address the user.
    """

    id: TransactionId
    payer_id: UserId
    amount: Money
    provider: Provider
    purpose: str
    status: Status
    external_id: str | None
    created_at: datetime
    updated_at: datetime
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False, compare=False)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    @classmethod
    def create_invoice(
        cls,
        payer_id: UserId,
        amount: Money,
        provider: Provider,
        purpose: str,
        now: datetime,
    ) -> "Transaction":
        return cls(
            id=TransactionId.new(),
            payer_id=payer_id,
            amount=amount,
            provider=provider,
            purpose=purpose,
            status=Status.PENDING,
            external_id=None,
            created_at=now,
            updated_at=now,
        )

    def can_refund(self) -> bool:
        return self.status == Status.PAID

    def mark_paid(self, external_id: str, now: datetime) -> None:
        if self.status != Status.PENDING:
            raise InvalidStatusTransition(f"Cannot mark {self.status} transaction as PAID")
        self.status = Status.PAID
        self.external_id = external_id
        self.updated_at = now
        self._events.append(
            PaymentConfirmed(
                transaction_id=self.id.value,
                payer_id=self.payer_id.value,
                purpose=self.purpose,
                occurred_at=now,
            )
        )

    def mark_failed(self, now: datetime) -> None:
        if self.status != Status.PENDING:
            raise InvalidStatusTransition(f"Cannot mark {self.status} transaction as FAILED")
        self.status = Status.FAILED
        self.updated_at = now

    def refund(self, now: datetime) -> None:
        if self.status != Status.PAID:
            raise InvalidStatusTransition(f"Cannot refund {self.status} transaction (must be PAID)")
        self.status = Status.REFUNDED
        self.updated_at = now
        self._events.append(
            PaymentRefunded(
                transaction_id=self.id.value,
                payer_id=self.payer_id.value,
                purpose=self.purpose,
                occurred_at=now,
            )
        )

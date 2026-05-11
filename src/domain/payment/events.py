from dataclasses import dataclass
from uuid import UUID

from src.domain.shared.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentConfirmed(DomainEvent):
    transaction_id: UUID
    payer_id: UUID
    purpose: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentRefunded(DomainEvent):
    transaction_id: UUID
    payer_id: UUID
    purpose: str

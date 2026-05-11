from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreatePremiumInvoiceRequest:
    payer_id: UUID
    payer_telegram_id: int
    tier: str  # "bronze" | "silver" | "gold"


@dataclass(frozen=True, slots=True)
class CreateInvoiceResponse:
    transaction_id: UUID
    provider: str
    amount: int
    currency: str
    payment_url: str | None  # None for Telegram Stars (invoice already sent in chat)


@dataclass(frozen=True, slots=True)
class ConfirmPaymentRequest:
    transaction_id: UUID
    external_id: str  # provider's charge id (e.g. telegram_payment_charge_id)


@dataclass(frozen=True, slots=True)
class RefundPaymentRequest:
    transaction_id: UUID

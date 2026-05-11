from dataclasses import dataclass
from typing import Protocol

from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import Provider


@dataclass(frozen=True, slots=True)
class PaymentInitiation:
    """Result of `IPaymentGateway.initiate_payment`.

    For Telegram Stars, the gateway sent the invoice to the user's chat —
    `payment_url` is None and the bot does not need to do anything.
    For URL-based providers, `payment_url` is the hosted payment page.
    """

    payment_url: str | None


class IPaymentGateway(Protocol):
    """Provider-agnostic side of the ACL.

    `payer_telegram_id` is named generically here because Telegram Stars is
    the only provider for now. When a second provider arrives, the right
    refactor is a `PaymentContext` value object that each gateway interprets
    on its own terms.
    """

    provider: Provider

    async def initiate_payment(
        self,
        transaction: Transaction,
        payer_telegram_id: int,
        title: str,
        description: str,
    ) -> PaymentInitiation: ...

    async def refund(
        self,
        external_id: str,
        payer_telegram_id: int,
    ) -> None: ...


class IPaymentGatewayRegistry(Protocol):
    def get(self, provider: Provider) -> IPaymentGateway: ...

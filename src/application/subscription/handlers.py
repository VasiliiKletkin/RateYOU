from dataclasses import dataclass

from src.domain.payment.events import PaymentConfirmed, PaymentRefunded
from src.domain.shared.identifiers import UserId
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import Tier


@dataclass
class OnPaymentConfirmed:
    """Activates the matching premium tier when a payment lands.

    Looks at `purpose` (convention: "premium:<tier>") to know what to do.
    Other purpose prefixes are ignored.
    """

    activation_service: SubscriptionActivationService

    async def handle(self, event: PaymentConfirmed) -> None:
        if not event.purpose.startswith("premium:"):
            return
        tier = Tier(event.purpose.removeprefix("premium:"))
        await self.activation_service.activate(
            UserId(event.payer_id),
            tier,
            event.occurred_at,
        )


@dataclass
class OnPaymentRefunded:
    """Revokes premium when the matching payment is refunded."""

    activation_service: SubscriptionActivationService

    async def handle(self, event: PaymentRefunded) -> None:
        if not event.purpose.startswith("premium:"):
            return
        await self.activation_service.revoke(
            UserId(event.payer_id),
            event.occurred_at,
        )

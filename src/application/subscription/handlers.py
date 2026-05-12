from dataclasses import dataclass

from src.domain.payment.events import PaymentConfirmed, PaymentRefunded
from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import Tier


@dataclass
class OnPaymentConfirmed:
    """Activates the matching premium tier when a payment lands.

    Looks at `purpose` (convention: "premium:<tier>") to know what to do.
    Other purpose prefixes are ignored. The grant is linked back to the
    paying transaction so a later refund can revoke just this grant.
    """

    activation_service: SubscriptionActivationService

    async def handle(self, event: PaymentConfirmed) -> None:
        if not event.purpose.startswith("premium:"):
            return
        tier = Tier(event.purpose.removeprefix("premium:"))
        await self.activation_service.activate_purchase(
            owner_id=UserId(event.payer_id),
            tier=tier,
            transaction_id=TransactionId(event.transaction_id),
            now=event.occurred_at,
        )


@dataclass
class OnPaymentRefunded:
    """Revokes the grant tied to the refunded transaction.

    Other grants of the same user (bonus days, a newer paid subscription)
    are untouched.
    """

    activation_service: SubscriptionActivationService

    async def handle(self, event: PaymentRefunded) -> None:
        if not event.purpose.startswith("premium:"):
            return
        await self.activation_service.revoke_for_transaction(
            transaction_id=TransactionId(event.transaction_id),
            now=event.occurred_at,
        )

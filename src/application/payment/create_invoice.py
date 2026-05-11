from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.payment.dto import CreateInvoiceResponse, CreatePremiumInvoiceRequest
from src.domain.payment.entities import Transaction
from src.domain.payment.gateway import IPaymentGatewayRegistry
from src.domain.payment.repositories import ITransactionRepository
from src.domain.payment.value_objects import Money, Provider
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.tier_catalog import get_tier_spec
from src.domain.subscription.value_objects import Tier


@dataclass
class CreatePremiumInvoiceUseCase:
    """Creates a Transaction (PENDING) and initiates payment via the gateway.

    `payer_telegram_id` is passed straight through to the gateway as the
    delivery address — domain `Transaction` doesn't store it.
    """

    transaction_repo: ITransactionRepository
    gateways: IPaymentGatewayRegistry
    uow: UnitOfWork

    async def execute(self, request: CreatePremiumInvoiceRequest) -> CreateInvoiceResponse:
        tier = Tier(request.tier)
        spec = get_tier_spec(tier)
        provider = Provider.TELEGRAM_STARS

        amount = Money(amount=spec.stars_price, currency="XTR")
        transaction = Transaction.create_invoice(
            payer_id=UserId(request.payer_id),
            amount=amount,
            provider=provider,
            purpose=f"premium:{tier.value}",
            now=datetime.now(UTC),
        )
        await self.transaction_repo.add(transaction)

        gateway = self.gateways.get(provider)
        initiation = await gateway.initiate_payment(
            transaction=transaction,
            payer_telegram_id=request.payer_telegram_id,
            title=f"Premium {spec.display_name}",
            description=f"{spec.duration_days} days of premium access",
        )

        await self.uow.commit()

        return CreateInvoiceResponse(
            transaction_id=transaction.id.value,
            provider=provider.value,
            amount=amount.amount,
            currency=amount.currency,
            payment_url=initiation.payment_url,
        )

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.payment.dto import RefundPaymentRequest
from src.domain.identity.repositories import IUserRepository
from src.domain.payment.exceptions import (
    InvalidStatusTransition,
    TransactionNotFound,
)
from src.domain.payment.gateway import IPaymentGatewayRegistry
from src.domain.payment.repositories import ITransactionRepository
from src.domain.payment.value_objects import TransactionId
from src.domain.shared.event_bus import IEventBus
from src.domain.shared.uow import UnitOfWork


@dataclass
class RefundPaymentUseCase:
    """Admin / refund flow.

    Looks up the payer's Telegram ID via `IUserRepository` (the ACL bridge:
    Payment domain doesn't carry Telegram fields), calls the provider's
    refund API, then marks the Transaction REFUNDED and publishes the event.
    Provider-side failure leaves DB untouched (no commit).
    """

    transaction_repo: ITransactionRepository
    user_repo: IUserRepository
    gateways: IPaymentGatewayRegistry
    event_bus: IEventBus
    uow: UnitOfWork

    async def execute(self, request: RefundPaymentRequest) -> None:
        transaction = await self.transaction_repo.get_by_id(TransactionId(request.transaction_id))
        if transaction is None:
            raise TransactionNotFound(f"Transaction {request.transaction_id} not found")
        if not transaction.can_refund():
            raise InvalidStatusTransition(
                f"Cannot refund transaction in status {transaction.status}"
            )
        assert transaction.external_id is not None

        payer = await self.user_repo.get_by_id(transaction.payer_id)
        if payer is None:
            raise TransactionNotFound(f"Payer {transaction.payer_id.value} not found for refund")

        gateway = self.gateways.get(transaction.provider)
        await gateway.refund(
            external_id=transaction.external_id,
            payer_telegram_id=payer.telegram_id.value,
        )

        transaction.refund(now=datetime.now(UTC))
        await self.transaction_repo.update(transaction)

        await self.event_bus.publish_all(transaction.pull_events())
        await self.uow.commit()

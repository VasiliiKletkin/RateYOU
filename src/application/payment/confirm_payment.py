from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.payment.dto import ConfirmPaymentRequest
from src.domain.payment.exceptions import TransactionNotFound
from src.domain.payment.repositories import ITransactionRepository
from src.domain.payment.value_objects import TransactionId
from src.domain.shared.event_bus import IEventBus
from src.domain.shared.uow import UnitOfWork


@dataclass
class ConfirmPaymentUseCase:
    """Called from the bot's `successful_payment` handler.

    Marks Transaction PAID and publishes `PaymentConfirmed`. The handler
    `OnPaymentConfirmed` (subscribed at DI level) activates premium in the
    same UoW so both writes commit atomically.
    """

    transaction_repo: ITransactionRepository
    event_bus: IEventBus
    uow: UnitOfWork

    async def execute(self, request: ConfirmPaymentRequest) -> None:
        transaction = await self.transaction_repo.get_by_id(
            TransactionId(request.transaction_id)
        )
        if transaction is None:
            raise TransactionNotFound(
                f"Transaction {request.transaction_id} not found"
            )

        transaction.mark_paid(external_id=request.external_id, now=datetime.now(UTC))
        await self.transaction_repo.update(transaction)

        await self.event_bus.publish_all(transaction.pull_events())
        await self.uow.commit()

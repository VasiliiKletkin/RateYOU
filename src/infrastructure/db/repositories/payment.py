from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import Money, TransactionId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.payment import TransactionORM


@dataclass
class TransactionRepository:
    session: AsyncSession

    async def add(self, transaction: Transaction) -> None:
        self.session.add(
            TransactionORM(
                id=transaction.id.value,
                payer_id=transaction.payer_id.value,
                amount=transaction.amount.amount,
                currency=transaction.amount.currency,
                provider=transaction.provider,
                purpose=transaction.purpose,
                status=transaction.status,
                external_id=transaction.external_id,
                created_at=transaction.created_at,
                updated_at=transaction.updated_at,
            )
        )
        await self.session.flush()

    async def get_by_id(self, transaction_id: TransactionId) -> Transaction | None:
        orm = await self.session.get(TransactionORM, transaction_id.value)
        if orm is None:
            return None
        return Transaction(
            id=TransactionId(orm.id),
            payer_id=UserId(orm.payer_id),
            amount=Money(amount=orm.amount, currency=orm.currency),
            provider=orm.provider,
            purpose=orm.purpose,
            status=orm.status,
            external_id=orm.external_id,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    async def update(self, transaction: Transaction) -> None:
        existing = await self.session.get(TransactionORM, transaction.id.value)
        if existing is None:
            raise ValueError(f"Transaction {transaction.id.value} not found for update")
        existing.status = transaction.status
        existing.external_id = transaction.external_id
        existing.updated_at = transaction.updated_at
        await self.session.flush()

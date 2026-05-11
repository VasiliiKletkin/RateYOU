from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import TransactionId
from src.infrastructure.db.mappers.payment import (
    orm_to_transaction,
    transaction_to_orm,
)
from src.infrastructure.db.models.payment import TransactionORM


@dataclass
class TransactionRepository:
    session: AsyncSession

    async def add(self, transaction: Transaction) -> None:
        self.session.add(transaction_to_orm(transaction))
        await self.session.flush()

    async def get_by_id(self, transaction_id: TransactionId) -> Transaction | None:
        orm = await self.session.get(TransactionORM, transaction_id.value)
        return orm_to_transaction(orm) if orm is not None else None

    async def update(self, transaction: Transaction) -> None:
        existing = await self.session.get(TransactionORM, transaction.id.value)
        if existing is None:
            raise ValueError(f"Transaction {transaction.id.value} not found for update")
        existing.status = transaction.status.value
        existing.external_id = transaction.external_id
        existing.updated_at = transaction.updated_at
        await self.session.flush()

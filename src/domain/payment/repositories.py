from typing import Protocol

from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import TransactionId


class ITransactionRepository(Protocol):
    async def add(self, transaction: Transaction) -> None: ...

    async def get_by_id(self, transaction_id: TransactionId) -> Transaction | None: ...

    async def update(self, transaction: Transaction) -> None: ...

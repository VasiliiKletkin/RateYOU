from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import (
    Money,
    Provider,
    Status,
    TransactionId,
)
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.payment import TransactionORM


def transaction_to_orm(transaction: Transaction) -> TransactionORM:
    return TransactionORM(
        id=transaction.id.value,
        payer_id=transaction.payer_id.value,
        amount=transaction.amount.amount,
        currency=transaction.amount.currency,
        provider=transaction.provider.value,
        purpose=transaction.purpose,
        status=transaction.status.value,
        external_id=transaction.external_id,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


def orm_to_transaction(orm: TransactionORM) -> Transaction:
    return Transaction(
        id=TransactionId(orm.id),
        payer_id=UserId(orm.payer_id),
        amount=Money(amount=orm.amount, currency=orm.currency),
        provider=Provider(orm.provider),
        purpose=orm.purpose,
        status=Status(orm.status),
        external_id=orm.external_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )

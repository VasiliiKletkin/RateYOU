from contextlib import suppress
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from src.application.payment.create_invoice import CreatePremiumInvoiceUseCase
from src.application.payment.dto import CreatePremiumInvoiceRequest
from src.domain.payment.entities import Transaction
from src.domain.payment.gateway import PaymentInitiation
from src.domain.payment.value_objects import Provider, TransactionId


@dataclass
class FakeTransactionRepository:
    transactions: dict[UUID, Transaction] = field(default_factory=dict)

    async def add(self, transaction: Transaction) -> None:
        self.transactions[transaction.id.value] = transaction

    async def get_by_id(self, transaction_id: TransactionId) -> Transaction | None:
        return self.transactions.get(transaction_id.value)

    async def update(self, transaction: Transaction) -> None:
        self.transactions[transaction.id.value] = transaction


@dataclass
class FakeTelegramStarsGateway:
    provider: Provider = Provider.TELEGRAM_STARS
    sent: list[tuple[Transaction, int]] = field(default_factory=list)
    fail: bool = False

    async def initiate_payment(
        self,
        transaction: Transaction,
        payer_telegram_id: int,
        title: str,
        description: str,
    ) -> PaymentInitiation:
        if self.fail:
            raise RuntimeError("gateway down")
        self.sent.append((transaction, payer_telegram_id))
        return PaymentInitiation(payment_url=None)

    async def refund(self, external_id: str, payer_telegram_id: int) -> None:
        pass


@dataclass
class FakeRegistry:
    gateway: FakeTelegramStarsGateway

    def get(self, provider: Provider) -> FakeTelegramStarsGateway:
        assert provider == self.gateway.provider
        return self.gateway


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


async def test_create_invoice_persists_pending_transaction_and_sends_to_gateway() -> None:
    repo = FakeTransactionRepository()
    gateway = FakeTelegramStarsGateway()
    uow = FakeUoW()
    use_case = CreatePremiumInvoiceUseCase(
        transaction_repo=repo,
        gateways=FakeRegistry(gateway),
        uow=uow,
    )

    response = await use_case.execute(
        CreatePremiumInvoiceRequest(
            payer_id=uuid4(),
            payer_telegram_id=12345,
            tier="silver",
        )
    )

    assert response.provider == "telegram_stars"
    assert response.currency == "XTR"
    assert response.amount == 300
    assert response.payment_url is None
    assert len(repo.transactions) == 1
    assert len(gateway.sent) == 1
    _, sent_to_telegram_id = gateway.sent[0]
    assert sent_to_telegram_id == 12345
    assert uow.committed is True

    [created] = repo.transactions.values()
    assert created.purpose == "premium:silver"
    assert created.status.value == "pending"


async def test_gateway_failure_does_not_commit() -> None:
    repo = FakeTransactionRepository()
    gateway = FakeTelegramStarsGateway(fail=True)
    uow = FakeUoW()
    use_case = CreatePremiumInvoiceUseCase(
        transaction_repo=repo,
        gateways=FakeRegistry(gateway),
        uow=uow,
    )

    with suppress(RuntimeError):
        await use_case.execute(
            CreatePremiumInvoiceRequest(
                payer_id=uuid4(),
                payer_telegram_id=12345,
                tier="bronze",
            )
        )

    assert uow.committed is False

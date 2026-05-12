"""End-to-end ConfirmPayment: Transaction PAID + Subscription activated via
the in-process event bus, all in one DB transaction.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.payment.confirm_payment import ConfirmPaymentUseCase
from src.application.payment.dto import ConfirmPaymentRequest
from src.application.subscription.get_premium import GetMyPremiumUseCase
from src.application.subscription.handlers import OnPaymentConfirmed
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.payment.entities import Transaction
from src.domain.payment.events import PaymentConfirmed
from src.domain.payment.value_objects import Money, Provider
from src.domain.subscription.services import SubscriptionActivationService
from src.infrastructure.db.repositories.payment import TransactionRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.infrastructure.events.in_memory_bus import InMemoryEventBus


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def _seed_pending_transaction(
    session: AsyncSession,
    user: User,
    tier: str,
    stars: int,
) -> Transaction:
    t = Transaction.create_invoice(
        payer_id=user.id,
        amount=Money(amount=stars, currency="XTR"),
        provider=Provider.TELEGRAM_STARS,
        purpose=f"premium:{tier}",
        now=datetime.now(UTC),
    )
    await TransactionRepository(session=session).add(t)
    return t


def _make_use_case(session: AsyncSession) -> ConfirmPaymentUseCase:
    activation = SubscriptionActivationService(
        subscription_repo=SubscriptionRepository(session=session),
    )
    handler = OnPaymentConfirmed(activation_service=activation)
    bus = InMemoryEventBus()
    bus.subscribe(PaymentConfirmed, handler.handle)
    return ConfirmPaymentUseCase(
        transaction_repo=TransactionRepository(session=session),
        event_bus=bus,
        uow=SqlAlchemyUnitOfWork(session=session),
    )


async def test_confirm_marks_paid_and_activates_premium_in_db(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, 8001)
    transaction = await _seed_pending_transaction(session, user, tier="silver", stars=300)
    use_case = _make_use_case(session)

    await use_case.execute(
        ConfirmPaymentRequest(
            transaction_id=transaction.id.value,
            external_id="tg-charge-1",
        )
    )

    refreshed = await TransactionRepository(session=session).get_by_id(transaction.id)
    assert refreshed is not None
    assert refreshed.status.value == "paid"
    assert refreshed.external_id == "tg-charge-1"

    premium = await GetMyPremiumUseCase(
        subscription_repo=SubscriptionRepository(session=session)
    ).execute(user.id.value)
    assert premium is not None
    assert premium.tier == "silver"


async def test_confirm_upgrades_existing_subscription(session: AsyncSession) -> None:
    """User buys Bronze, then later Gold — second purchase replaces tier."""
    user = await _seed_user(session, 8002)

    bronze_tx = await _seed_pending_transaction(session, user, tier="bronze", stars=100)
    await _make_use_case(session).execute(
        ConfirmPaymentRequest(transaction_id=bronze_tx.id.value, external_id="ch-1")
    )

    gold_tx = await _seed_pending_transaction(session, user, tier="gold", stars=1000)
    await _make_use_case(session).execute(
        ConfirmPaymentRequest(transaction_id=gold_tx.id.value, external_id="ch-2")
    )

    premium = await GetMyPremiumUseCase(
        subscription_repo=SubscriptionRepository(session=session)
    ).execute(user.id.value)
    assert premium is not None
    assert premium.tier == "gold"

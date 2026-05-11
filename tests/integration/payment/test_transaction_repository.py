from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.payment.entities import Transaction
from src.domain.payment.value_objects import Money, Provider, Status
from src.infrastructure.db.repositories.payment import TransactionRepository
from src.infrastructure.db.repositories.user import UserRepository


async def _seed_user(session: AsyncSession, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    await UserRepository(session=session).add(user)
    return user


async def test_add_and_get_by_id_roundtrip(session: AsyncSession) -> None:
    user = await _seed_user(session, 7001)
    repo = TransactionRepository(session=session)
    t = Transaction.create_invoice(
        payer_id=user.id,
        amount=Money(amount=300, currency="XTR"),
        provider=Provider.TELEGRAM_STARS,
        purpose="premium:silver",
        now=datetime.now(UTC),
    )

    await repo.add(t)

    found = await repo.get_by_id(t.id)
    assert found is not None
    assert found.payer_id == user.id
    assert found.amount == Money(amount=300, currency="XTR")
    assert found.status == Status.PENDING
    assert found.external_id is None


async def test_update_persists_state_transition(session: AsyncSession) -> None:
    user = await _seed_user(session, 7002)
    repo = TransactionRepository(session=session)
    now = datetime.now(UTC)
    t = Transaction.create_invoice(
        payer_id=user.id,
        amount=Money(amount=100, currency="XTR"),
        provider=Provider.TELEGRAM_STARS,
        purpose="premium:bronze",
        now=now,
    )
    await repo.add(t)

    t.mark_paid(external_id="tg-charge-1", now=now)
    await repo.update(t)

    refreshed = await repo.get_by_id(t.id)
    assert refreshed is not None
    assert refreshed.status == Status.PAID
    assert refreshed.external_id == "tg-charge-1"

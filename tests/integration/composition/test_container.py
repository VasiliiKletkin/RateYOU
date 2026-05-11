"""Smoke tests for the dishka DI container.

Verifies that the full provider graph assembles and can resolve use cases
end-to-end — including the Payment use case, which transitively requires
the Bot and the TelegramStarsGateway. This catches missing or mistyped
provider registrations that mypy alone wouldn't notice.
"""

from aiogram.fsm.storage.base import BaseStorage
from dishka import make_async_container

from src.application.identity.register_user import RegisterUserUseCase
from src.application.payment.create_invoice import CreatePremiumInvoiceUseCase
from src.application.rating.rate_user import RateUserUseCase
from src.application.subscription.list_tiers import ListTiersUseCase
from src.presentation.di import all_providers


async def test_container_resolves_identity_use_case() -> None:
    container = make_async_container(*all_providers())
    try:
        async with container() as request:
            uc = await request.get(RegisterUserUseCase)
            assert isinstance(uc, RegisterUserUseCase)
    finally:
        await container.close()


async def test_container_resolves_rating_use_case() -> None:
    container = make_async_container(*all_providers())
    try:
        async with container() as request:
            uc = await request.get(RateUserUseCase)
            assert isinstance(uc, RateUserUseCase)
    finally:
        await container.close()


async def test_container_resolves_payment_use_case_with_gateway() -> None:
    """The deepest dependency chain: Use case → Registry → Gateway → Bot."""
    container = make_async_container(*all_providers())
    try:
        async with container() as request:
            uc = await request.get(CreatePremiumInvoiceUseCase)
            assert isinstance(uc, CreatePremiumInvoiceUseCase)
    finally:
        await container.close()


async def test_container_resolves_parameterless_use_case() -> None:
    container = make_async_container(*all_providers())
    try:
        async with container() as request:
            uc = await request.get(ListTiersUseCase)
            assert isinstance(uc, ListTiersUseCase)
    finally:
        await container.close()


async def test_container_resolves_fsm_storage() -> None:
    """FSM storage chain: BaseStorage -> RedisStorage -> Redis client."""
    container = make_async_container(*all_providers())
    try:
        storage = await container.get(BaseStorage)
        assert storage is not None
    finally:
        await container.close()

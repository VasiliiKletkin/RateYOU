from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.exceptions import SubscriptionNotFound
from src.domain.subscription.repositories import ISubscriptionRepository
from src.domain.subscription.services import SubscriptionActivationService


@dataclass
class RevokePremiumUseCase:
    """Admin / refund flow: ends premium immediately."""

    subscription_repo: ISubscriptionRepository
    activation_service: SubscriptionActivationService
    uow: UnitOfWork

    async def execute(self, owner_id: UUID) -> None:
        owner = UserId(owner_id)
        if (await self.subscription_repo.get_for(owner)) is None:
            raise SubscriptionNotFound(f"No subscription for {owner_id}")
        await self.activation_service.revoke(owner, datetime.now(UTC))
        await self.uow.commit()

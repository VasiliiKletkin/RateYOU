from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.entities import SubscriptionStatus
from src.domain.subscription.exceptions import SubscriptionNotFound
from src.domain.subscription.repositories import ISubscriptionRepository
from src.domain.subscription.services import SubscriptionActivationService


@dataclass
class RevokePremiumUseCase:
    """Admin "kill premium now" flow.

    Revokes every currently-active grant of the owner. If the owner has no
    active grants at all, raises `SubscriptionNotFound` so the caller (admin
    UI / script) sees a clear error instead of a silent no-op.
    """

    subscription_repo: ISubscriptionRepository
    activation_service: SubscriptionActivationService
    uow: UnitOfWork

    async def execute(self, owner_id: UUID) -> None:
        owner = UserId(owner_id)
        now = datetime.now(UTC)
        grants = await self.subscription_repo.list_for(owner)
        if not SubscriptionStatus.from_grants(grants, now).is_active:
            raise SubscriptionNotFound(f"No active subscription for {owner_id}")
        await self.activation_service.revoke_all_active(owner, now)
        await self.uow.commit()

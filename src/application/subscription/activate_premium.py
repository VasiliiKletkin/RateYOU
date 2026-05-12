from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.subscription.dto import ActivatePremiumRequest, PremiumResponse
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import Tier


@dataclass
class ActivatePremiumUseCase:
    """Activates premium for the user with the given tier.

    Replace policy: a fresh `duration_days` from now, regardless of what
    the user had before. Old remaining time is forfeited.
    """

    activation_service: SubscriptionActivationService
    uow: UnitOfWork

    async def execute(self, request: ActivatePremiumRequest) -> PremiumResponse:
        owner_id = UserId(request.owner_id)
        tier = Tier(request.tier)
        now = datetime.now(UTC)

        sub = await self.activation_service.activate(owner_id, tier, now)
        await self.uow.commit()

        return PremiumResponse(
            owner_id=sub.owner_id.value,
            tier=sub.tier.value,
            expires_at=sub.expires_at,
            days_remaining=max(0, (sub.expires_at - now).days),
        )

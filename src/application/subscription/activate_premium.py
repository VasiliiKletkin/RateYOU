from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.subscription.dto import ActivatePremiumRequest, PremiumResponse
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.services import SubscriptionActivationService
from src.domain.subscription.value_objects import Tier


@dataclass
class ActivatePremiumUseCase:
    """Admin-direct premium activation (no payment flow).

    Creates a PURCHASE grant with `transaction_id=None`. Existing active
    PURCHASE grants of the same owner are revoked (the long-standing
    "remaining paid days are forfeited" rule). BONUS grants are untouched.
    """

    activation_service: SubscriptionActivationService
    uow: UnitOfWork

    async def execute(self, request: ActivatePremiumRequest) -> PremiumResponse:
        owner_id = UserId(request.owner_id)
        tier = Tier(request.tier)
        now = datetime.now(UTC)

        grant = await self.activation_service.activate_purchase(
            owner_id=owner_id,
            tier=tier,
            transaction_id=None,
            now=now,
        )
        await self.uow.commit()

        return PremiumResponse(
            owner_id=grant.owner_id.value,
            tier=grant.tier.value,
            expires_at=grant.expires_at,
            days_remaining=max(0, (grant.expires_at - now).days),
        )

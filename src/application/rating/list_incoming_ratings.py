from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.rating.dto import IncomingRatingItem, IncomingRatingsResponse
from src.domain.profile.repositories import IProfileRepository
from src.domain.rating.repositories import IRatingRepository
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import SubscriptionStatus
from src.domain.subscription.exceptions import PremiumRequired
from src.domain.subscription.repositories import ISubscriptionRepository

DEFAULT_LIMIT = 10


@dataclass
class ListIncomingRatingsUseCase:
    """Premium-gated read: who recently rated me.

    Raises `PremiumRequired` if the viewer has no active subscription.
    Rater names come from each rater's Profile; raters without a profile
    are returned as `rater_name=None` so the presentation layer can pick
    a localized placeholder.
    """

    subscription_repo: ISubscriptionRepository
    rating_repo: IRatingRepository
    profile_repo: IProfileRepository

    async def execute(
        self,
        viewer_id: UUID,
        limit: int = DEFAULT_LIMIT,
    ) -> IncomingRatingsResponse:
        viewer = UserId(viewer_id)

        grants = await self.subscription_repo.list_for(viewer)
        if not SubscriptionStatus.from_grants(grants, datetime.now(UTC)).is_active:
            raise PremiumRequired

        ratings = await self.rating_repo.list_for_rated(viewer, limit)

        items: list[IncomingRatingItem] = []
        for rating in ratings:
            profile = await self.profile_repo.get_by_owner_id(rating.rater_id)
            items.append(
                IncomingRatingItem(
                    rater_name=profile.name.value if profile is not None else None,
                    score=rating.score.value,
                    rated_at=rating.created_at,
                )
            )

        return IncomingRatingsResponse(items=tuple(items))

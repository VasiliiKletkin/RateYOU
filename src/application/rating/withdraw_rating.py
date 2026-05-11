from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.domain.rating.exceptions import RatingNotFound
from src.domain.rating.services import RatingFulfillmentService
from src.domain.shared.event_bus import IEventBus
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class WithdrawRatingUseCase:
    fulfillment_service: RatingFulfillmentService
    event_bus: IEventBus
    uow: UnitOfWork

    async def execute(self, rater_id: UUID, rated_id: UUID) -> None:
        rating = await self.fulfillment_service.withdraw(
            rater_id=UserId(rater_id),
            rated_id=UserId(rated_id),
            now=datetime.now(UTC),
        )
        if rating is None:
            raise RatingNotFound(f"No rating by {rater_id} of {rated_id}")
        await self.event_bus.publish_all(rating.pull_events())
        await self.uow.commit()

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.rating.dto import RateUserRequest, RatingResponse
from src.domain.rating.services import RatingFulfillmentService
from src.domain.rating.value_objects import Score
from src.domain.referral.services import ReferralRewardService
from src.domain.shared.event_bus import IEventBus
from src.domain.shared.identifiers import UserId
from src.domain.shared.uow import UnitOfWork


@dataclass
class RateUserUseCase:
    """Idempotent on (rater, rated) — re-rating updates the score.

    Publishes `RatingGiven` via the event bus so the
    `ProfileScoreSummary` projection updates in the same UoW.

    Also signals the Referral context that the rater submitted a rating;
    the service flips its internal `first_rating_given` flag once and is a
    no-op on every subsequent call, so calling it on every rate is cheap
    even for non-referred users.
    """

    fulfillment_service: RatingFulfillmentService
    referral_service: ReferralRewardService
    event_bus: IEventBus
    uow: UnitOfWork

    async def execute(self, request: RateUserRequest) -> RatingResponse:
        rater_id = UserId(request.rater_id)
        now = datetime.now(UTC)
        rating = await self.fulfillment_service.rate(
            rater_id=rater_id,
            rated_id=UserId(request.rated_id),
            score=Score(request.score),
            now=now,
        )
        await self.event_bus.publish_all(rating.pull_events())
        await self.referral_service.mark_first_rating(rater_id, now)
        await self.uow.commit()

        return RatingResponse(
            id=rating.id.value,
            rater_id=rating.rater_id.value,
            rated_id=rating.rated_id.value,
            score=rating.score.value,
        )

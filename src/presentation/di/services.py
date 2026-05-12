from dishka import Provider, Scope, provide

from src.domain.rating.services import RatingFulfillmentService
from src.domain.referral.services import ReferralRewardService
from src.domain.subscription.services import SubscriptionActivationService


class DomainServiceProvider(Provider):
    """Wires domain services at REQUEST scope.

    Domain services own cross-aggregate or cross-projection logic but don't
    commit themselves — the use cases above them do. They take repository
    Protocols, which dishka resolves from `RepositoryProvider`.
    """

    scope = Scope.REQUEST

    rating_fulfillment = provide(RatingFulfillmentService)
    subscription_activation = provide(SubscriptionActivationService)
    referral_reward = provide(ReferralRewardService)

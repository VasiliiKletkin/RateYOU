from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import Tier
from src.infrastructure.db.models.subscription import SubscriptionORM


def subscription_to_orm(subscription: Subscription) -> SubscriptionORM:
    return SubscriptionORM(
        owner_id=subscription.owner_id.value,
        tier=subscription.tier.value,
        expires_at=subscription.expires_at,
        is_revoked=subscription.is_revoked,
        updated_at=subscription.updated_at,
    )


def orm_to_subscription(orm: SubscriptionORM) -> Subscription:
    return Subscription(
        owner_id=UserId(orm.owner_id),
        tier=Tier(orm.tier),
        expires_at=orm.expires_at,
        is_revoked=orm.is_revoked,
        updated_at=orm.updated_at,
    )

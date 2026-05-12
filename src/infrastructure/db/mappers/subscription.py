from src.domain.payment.value_objects import TransactionId
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionId
from src.infrastructure.db.models.subscription import SubscriptionORM


def subscription_to_orm(grant: Subscription) -> SubscriptionORM:
    return SubscriptionORM(
        id=grant.id.value,
        owner_id=grant.owner_id.value,
        tier=grant.tier,
        source=grant.source,
        transaction_id=(
            grant.transaction_id.value if grant.transaction_id is not None else None
        ),
        starts_at=grant.starts_at,
        expires_at=grant.expires_at,
        is_revoked=grant.is_revoked,
        created_at=grant.created_at,
    )


def orm_to_subscription(orm: SubscriptionORM) -> Subscription:
    return Subscription(
        id=SubscriptionId(orm.id),
        owner_id=UserId(orm.owner_id),
        tier=orm.tier,
        source=orm.source,
        transaction_id=(
            TransactionId(orm.transaction_id) if orm.transaction_id is not None else None
        ),
        starts_at=orm.starts_at,
        expires_at=orm.expires_at,
        is_revoked=orm.is_revoked,
        created_at=orm.created_at,
    )

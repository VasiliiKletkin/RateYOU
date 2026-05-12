from src.domain.referral.entities import Referral
from src.domain.referral.value_objects import ReferralId, ReferralStatus
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.referral import ReferralORM


def referral_to_orm(referral: Referral) -> ReferralORM:
    return ReferralORM(
        id=referral.id.value,
        referrer_id=referral.referrer_id.value,
        referee_id=referral.referee_id.value,
        status=referral.status.value,
        profile_created=referral.profile_created,
        first_rating_given=referral.first_rating_given,
        created_at=referral.created_at,
        qualified_at=referral.qualified_at,
        rewarded_at=referral.rewarded_at,
    )


def orm_to_referral(orm: ReferralORM) -> Referral:
    return Referral(
        id=ReferralId(orm.id),
        referrer_id=UserId(orm.referrer_id),
        referee_id=UserId(orm.referee_id),
        status=ReferralStatus(orm.status),
        profile_created=orm.profile_created,
        first_rating_given=orm.first_rating_given,
        created_at=orm.created_at,
        qualified_at=orm.qualified_at,
        rewarded_at=orm.rewarded_at,
    )

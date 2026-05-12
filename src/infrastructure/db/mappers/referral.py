from src.domain.referral.entities import Referral
from src.domain.referral.value_objects import ReferralId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.referral import ReferralORM


def referral_to_orm(referral: Referral) -> ReferralORM:
    return ReferralORM(
        id=referral.id.value,
        referrer_id=referral.referrer_id.value,
        referee_id=referral.referee_id.value,
        created_at=referral.created_at,
        rewarded_at=referral.rewarded_at,
    )


def orm_to_referral(orm: ReferralORM) -> Referral:
    return Referral(
        id=ReferralId(orm.id),
        referrer_id=UserId(orm.referrer_id),
        referee_id=UserId(orm.referee_id),
        created_at=orm.created_at,
        rewarded_at=orm.rewarded_at,
    )

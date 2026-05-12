from src.domain.identity.entities import User
from src.domain.identity.value_objects import ReferralCode, Role, TelegramId
from src.domain.shared.identifiers import UserId
from src.infrastructure.db.models.identity import UserORM


def user_to_orm(user: User) -> UserORM:
    return UserORM(
        id=user.id.value,
        telegram_id=user.telegram_id.value,
        role=user.role.value,
        is_banned=user.is_banned,
        ban_reason=user.ban_reason,
        banned_at=user.banned_at,
        language=user.language,
        referral_code=user.referral_code.value,
        referred_by_user_id=(
            user.referred_by_user_id.value
            if user.referred_by_user_id is not None
            else None
        ),
        created_at=user.created_at,
    )


def orm_to_user(orm: UserORM) -> User:
    return User(
        id=UserId(orm.id),
        telegram_id=TelegramId(orm.telegram_id),
        role=Role(orm.role),
        is_banned=orm.is_banned,
        ban_reason=orm.ban_reason,
        banned_at=orm.banned_at,
        language=orm.language,
        referral_code=ReferralCode(orm.referral_code),
        referred_by_user_id=(
            UserId(orm.referred_by_user_id)
            if orm.referred_by_user_id is not None
            else None
        ),
        created_at=orm.created_at,
    )

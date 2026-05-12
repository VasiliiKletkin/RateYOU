from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest, UserResponse
from src.domain.identity.entities import User
from src.domain.identity.exceptions import InvalidReferralCode
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import ReferralCode, TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.repositories import IReferralRepository
from src.domain.shared.uow import UnitOfWork


@dataclass
class RegisterUserUseCase:
    """Idempotent: if a user with this telegram_id already exists, return them.

    Called on /start. Always returns a valid user view, regardless of whether
    they were just created or already existed.

    If a valid `referral_code` is supplied for a new user, the use case also
    sets `User.referred_by_user_id` and creates a PENDING Referral. Malformed
    codes, unknown codes, and self-referral are silently ignored — the
    registration always succeeds; only the link is dropped.
    """

    user_repo: IUserRepository
    referral_repo: IReferralRepository
    uow: UnitOfWork

    async def execute(self, request: RegisterUserRequest) -> UserResponse:
        telegram_id = TelegramId(request.telegram_id)

        existing = await self.user_repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            # `User.language` is owned by the user once registered (settable
            # via /settings, read by the i18n middleware). The Telegram code
            # passed in `request.language` is only useful for the new-user
            # branch below — never overwrites a returning user's preference.
            # Referral codes are also dropped: a returning user is not a new
            # referee.
            return _to_response(existing)

        now = datetime.now(UTC)
        referrer = await self._resolve_referrer(request.referral_code)

        user = User.register(
            telegram_id=telegram_id,
            now=now,
            language=request.language or "en",
            referred_by=referrer.id if referrer is not None else None,
        )
        await self.user_repo.add(user)

        if referrer is not None and referrer.id != user.id:
            referral = Referral.create_pending(
                referrer_id=referrer.id,
                referee_id=user.id,
                now=now,
            )
            await self.referral_repo.add(referral)

        await self.uow.commit()
        return _to_response(user)

    async def _resolve_referrer(self, code_str: str | None) -> User | None:
        if not code_str:
            return None
        try:
            code = ReferralCode(code_str)
        except InvalidReferralCode:
            return None
        return await self.user_repo.get_by_referral_code(code)


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id.value,
        telegram_id=user.telegram_id.value,
        is_banned=user.is_banned,
        is_admin=user.is_admin,
        language=user.language,
    )

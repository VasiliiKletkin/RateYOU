from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest, UserResponse
from src.domain.identity.entities import User
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import Language, TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.repositories import IReferralRepository
from src.domain.shared.uow import UnitOfWork


@dataclass
class RegisterUserUseCase:
    """Idempotent: if a user with this telegram_id already exists, return them.

    Called on /start. Always returns a valid user view, regardless of whether
    they were just created or already existed.

    When the start payload carries a referrer Telegram ID, the use case
    resolves it to a User and creates a **pending** ``Referral`` row
    (``rewarded_at=None``) linking referrer → new user — but only on the
    new-user branch. Returning users keep whatever link they had (or none).
    Unknown / self-pointing payloads are silently dropped; the registration
    always succeeds.

    The pending Referral is later promoted to "rewarded" by
    ``ReferralRewardService.mark_profile_created`` when the referee
    creates their profile.
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
            # Referrer payloads are also dropped: a returning user is not a
            # new referee.
            return _to_response(existing)

        now = datetime.now(UTC)
        referrer = await self._resolve_referrer(
            request.referrer_telegram_id, self_telegram_id=request.telegram_id
        )

        user = User.register(
            telegram_id=telegram_id,
            now=now,
            language=request.language or Language.EN,
        )
        await self.user_repo.add(user)

        if referrer is not None:
            await self.referral_repo.add(
                Referral.create_pending(
                    referrer_id=referrer.id,
                    referee_id=user.id,
                    now=now,
                )
            )

        await self.uow.commit()
        return _to_response(user)

    async def _resolve_referrer(
        self,
        referrer_telegram_id: int | None,
        self_telegram_id: int,
    ) -> User | None:
        if referrer_telegram_id is None:
            return None
        if referrer_telegram_id == self_telegram_id:
            return None  # Self-referral is silently dropped.
        try:
            tg = TelegramId(referrer_telegram_id)
        except ValueError:
            return None
        return await self.user_repo.get_by_telegram_id(tg)


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id.value,
        telegram_id=user.telegram_id.value,
        is_banned=user.is_banned,
        is_admin=user.is_admin,
        language=user.language,
    )

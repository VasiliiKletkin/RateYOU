from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest, UserResponse
from src.domain.identity.entities import User, normalize_username
from src.domain.identity.repositories import IUserRepository
from src.domain.identity.value_objects import Language, TelegramId
from src.domain.referral.entities import Referral
from src.domain.referral.repositories import IReferralRepository
from src.domain.shared.uow import UnitOfWork
from src.domain.subscription.entities import Subscription
from src.domain.subscription.repositories import ISubscriptionRepository

# Every newly registered user gets a month of premium on the house, granted
# as a BONUS Subscription — the same shape referral rewards use, so it shows
# up in /premium and expires on its own without any scheduled job.
WELCOME_BONUS_DAYS = 30


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

    New users also receive a ``WELCOME_BONUS_DAYS`` premium grant. It rides
    the new-user branch only, so the idempotent early return above doubles as
    the guard against handing out a second month on every later /start.
    """

    user_repo: IUserRepository
    referral_repo: IReferralRepository
    subscription_repo: ISubscriptionRepository
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
            #
            # The @username is the exception: it belongs to Telegram, not to
            # us, so refresh the cached copy whenever the caller hands us a
            # fresh one. Written only on an actual change to keep /start free
            # of pointless UPDATEs.
            if (
                request.username is not None
                and normalize_username(request.username) != existing.username
            ):
                existing.set_username(request.username)
                await self.user_repo.update(existing)
                await self.uow.commit()
            return UserResponse(
                id=existing.id.value,
                telegram_id=existing.telegram_id.value,
                is_banned=existing.is_banned,
                is_admin=existing.is_admin,
                language=existing.language,
                notifications_enabled=existing.notifications_enabled,
            )

        now = datetime.now(UTC)
        referrer = await self._resolve_referrer(
            request.referrer_telegram_id, self_telegram_id=request.telegram_id
        )

        user = User.register(
            telegram_id=telegram_id,
            now=now,
            language=request.language or Language.EN,
            username=request.username,
        )
        await self.user_repo.add(user)

        # Welcome gift. Same transaction as the user row: either both land or
        # neither does, so nobody ends up registered without their bonus.
        await self.subscription_repo.add(
            Subscription.create_bonus(
                owner_id=user.id,
                duration_days=WELCOME_BONUS_DAYS,
                now=now,
            )
        )

        if referrer is not None:
            await self.referral_repo.add(
                Referral.create_pending(
                    referrer_id=referrer.id,
                    referee_id=user.id,
                    now=now,
                )
            )

        await self.uow.commit()
        return UserResponse(
            id=user.id.value,
            telegram_id=user.telegram_id.value,
            is_banned=user.is_banned,
            is_admin=user.is_admin,
            language=user.language,
            notifications_enabled=user.notifications_enabled,
        )

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

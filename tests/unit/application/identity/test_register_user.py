from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId


@dataclass
class FakeUserRepository:
    users: dict[UserId, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        for u in self.users.values():
            if u.telegram_id == telegram_id:
                return u
        return None

    async def update(self, user: User) -> None:
        self.users[user.id] = user


@dataclass
class FakeReferralRepo:
    referrals: list[Referral] = field(default_factory=list)

    async def add(self, r: Referral) -> None:
        self.referrals.append(r)

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        for r in self.referrals:
            if r.referee_id == referee_id:
                return r
        return None

    async def update(self, r: Referral) -> None:
        for idx, existing in enumerate(self.referrals):
            if existing.id == r.id:
                self.referrals[idx] = r
                return

    async def count_total_for_referrer(self, referrer_id: UserId) -> int:
        return sum(1 for r in self.referrals if r.referrer_id == referrer_id)

    async def count_rewarded_for_referrer(self, referrer_id: UserId) -> int:
        return sum(1 for r in self.referrals if r.referrer_id == referrer_id and r.is_rewarded)


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_use_case(
    users: FakeUserRepository | None = None,
    referrals: FakeReferralRepo | None = None,
    uow: FakeUoW | None = None,
) -> tuple[RegisterUserUseCase, FakeUserRepository, FakeReferralRepo, FakeUoW]:
    users = users or FakeUserRepository()
    referrals = referrals or FakeReferralRepo()
    uow = uow or FakeUoW()
    return (
        RegisterUserUseCase(user_repo=users, referral_repo=referrals, uow=uow),
        users,
        referrals,
        uow,
    )


def _seed_user(repo: FakeUserRepository, tg_id: int) -> User:
    user = User.register(TelegramId(tg_id), datetime.now(UTC))
    repo.users[user.id] = user
    return user


async def test_register_creates_new_user() -> None:
    use_case, repo, referrals, uow = _make_use_case()

    response = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert response.telegram_id == 12345
    assert response.is_banned is False
    assert response.is_admin is False
    assert uow.committed is True
    assert len(repo.users) == 1
    assert referrals.referrals == []  # no referrer → no Referral row


async def test_register_is_idempotent() -> None:
    use_case, repo, _, uow = _make_use_case()

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    uow.committed = False
    second = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert first.id == second.id
    assert len(repo.users) == 1
    assert uow.committed is False


async def test_register_with_valid_referrer_creates_pending_referral() -> None:
    use_case, repo, referrals, _ = _make_use_case()
    inviter = _seed_user(repo, 111)

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=inviter.telegram_id.value,
        )
    )

    assert len(referrals.referrals) == 1
    pending = referrals.referrals[0]
    assert pending.referrer_id == inviter.id
    assert pending.referee_id == UserId(response.id)
    assert pending.rewarded_at is None
    assert pending.is_rewarded is False


async def test_register_with_unknown_referrer_creates_no_referral() -> None:
    use_case, _, referrals, _ = _make_use_case()

    await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=999999999,
        )
    )

    assert referrals.referrals == []


async def test_register_with_self_referral_creates_no_referral() -> None:
    use_case, _, referrals, _ = _make_use_case()

    await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=12345,
        )
    )

    assert referrals.referrals == []


async def test_register_with_invalid_referrer_id_creates_no_referral() -> None:
    use_case, _, referrals, _ = _make_use_case()

    await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=-1,  # TelegramId rejects non-positive values
        )
    )

    assert referrals.referrals == []


async def test_returning_user_with_referrer_payload_ignores_it() -> None:
    use_case, _, referrals, _ = _make_use_case()
    inviter_tg = 111
    _seed_user(use_case.user_repo, inviter_tg)  # type: ignore[arg-type]

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    second = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=inviter_tg,
        )
    )

    assert first.id == second.id
    assert referrals.referrals == []

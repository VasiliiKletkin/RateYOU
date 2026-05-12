from dataclasses import dataclass, field
from uuid import UUID

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import RegisterUserUseCase
from src.domain.identity.entities import User
from src.domain.identity.value_objects import ReferralCode, TelegramId
from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId


@dataclass
class FakeUserRepository:
    users: dict[UUID, User] = field(default_factory=dict)

    async def add(self, user: User) -> None:
        self.users[user.id.value] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id.value)

    async def get_by_telegram_id(self, telegram_id: TelegramId) -> User | None:
        for u in self.users.values():
            if u.telegram_id == telegram_id:
                return u
        return None

    async def get_by_referral_code(self, code: ReferralCode) -> User | None:
        for u in self.users.values():
            if u.referral_code == code:
                return u
        return None

    async def update(self, user: User) -> None:
        self.users[user.id.value] = user


@dataclass
class FakeReferralRepository:
    referrals: list[Referral] = field(default_factory=list)

    async def add(self, referral: Referral) -> None:
        self.referrals.append(referral)

    async def get_by_referee(self, referee_id: UserId) -> Referral | None:
        for r in self.referrals:
            if r.referee_id == referee_id:
                return r
        return None

    async def list_by_referrer(self, referrer_id: UserId) -> list[Referral]:
        return [r for r in self.referrals if r.referrer_id == referrer_id]

    async def update(self, referral: Referral) -> None:
        for idx, existing in enumerate(self.referrals):
            if existing.id == referral.id:
                self.referrals[idx] = referral
                return


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_use_case(
    users: FakeUserRepository | None = None,
    referrals: FakeReferralRepository | None = None,
    uow: FakeUoW | None = None,
) -> tuple[RegisterUserUseCase, FakeUserRepository, FakeReferralRepository, FakeUoW]:
    users = users or FakeUserRepository()
    referrals = referrals or FakeReferralRepository()
    uow = uow or FakeUoW()
    uc = RegisterUserUseCase(user_repo=users, referral_repo=referrals, uow=uow)
    return uc, users, referrals, uow


async def test_register_creates_new_user() -> None:
    use_case, repo, _, uow = _make_use_case()

    response = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert response.telegram_id == 12345
    assert response.is_banned is False
    assert response.is_admin is False
    assert uow.committed is True
    assert len(repo.users) == 1
    # A code was assigned on register, regardless of payload.
    created = next(iter(repo.users.values()))
    assert len(created.referral_code.value) == 8


async def test_register_is_idempotent() -> None:
    use_case, repo, _, uow = _make_use_case()

    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    uow.committed = False
    second = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert first.id == second.id
    assert len(repo.users) == 1
    assert uow.committed is False


async def test_register_with_valid_referral_code_creates_pending_link() -> None:
    use_case, repo, referrals, _ = _make_use_case()
    # Seed an inviter user.
    inviter = await _seed_user(repo, telegram_id=111)

    response = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referral_code=inviter.referral_code.value,
        )
    )

    referee = repo.users[response.id]
    assert referee.referred_by_user_id == inviter.id
    assert len(referrals.referrals) == 1
    pending = referrals.referrals[0]
    assert pending.referrer_id == inviter.id
    assert pending.referee_id == referee.id
    assert pending.status.value == "pending"


async def test_register_with_malformed_code_succeeds_without_referral() -> None:
    use_case, repo, referrals, _ = _make_use_case()

    response = await use_case.execute(
        RegisterUserRequest(telegram_id=12345, referral_code="not-8-chars")
    )

    created = repo.users[response.id]
    assert created.referred_by_user_id is None
    assert referrals.referrals == []


async def test_register_with_unknown_code_succeeds_without_referral() -> None:
    use_case, repo, referrals, _ = _make_use_case()

    response = await use_case.execute(
        RegisterUserRequest(telegram_id=12345, referral_code="abcd1234")
    )

    created = repo.users[response.id]
    assert created.referred_by_user_id is None
    assert referrals.referrals == []


async def test_returning_user_with_referral_code_ignores_code() -> None:
    use_case, repo, referrals, _ = _make_use_case()
    inviter = await _seed_user(repo, telegram_id=111)

    # First registration — no code, so no referral link.
    first = await use_case.execute(RegisterUserRequest(telegram_id=12345))
    # Returning /start ref_<code> must NOT retroactively link.
    second = await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referral_code=inviter.referral_code.value,
        )
    )

    assert first.id == second.id
    returning = repo.users[second.id]
    assert returning.referred_by_user_id is None
    assert referrals.referrals == []


async def _seed_user(repo: FakeUserRepository, telegram_id: int) -> User:
    from datetime import UTC, datetime

    user = User.register(TelegramId(telegram_id), datetime.now(UTC))
    await repo.add(user)
    return user

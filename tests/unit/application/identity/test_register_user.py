from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.application.identity.dto import RegisterUserRequest
from src.application.identity.register_user import WELCOME_BONUS_DAYS, RegisterUserUseCase
from src.domain.identity.entities import Acquisition, User
from src.domain.identity.value_objects import TelegramId
from src.domain.payment.value_objects import TransactionId
from src.domain.referral.entities import Referral
from src.domain.shared.identifiers import UserId
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import SubscriptionSource, Tier


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

    async def list_by_ids(self, user_ids: list[UserId]) -> list[User]:
        return [self.users[uid] for uid in user_ids if uid in self.users]


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
class FakeSubscriptionRepo:
    grants: list[Subscription] = field(default_factory=list)

    async def add(self, grant: Subscription) -> None:
        self.grants.append(grant)

    async def list_for(self, owner_id: UserId) -> list[Subscription]:
        return [g for g in self.grants if g.owner_id == owner_id]

    # Unused-but-required:
    async def list_active_purchases_for(
        self, owner_id: UserId, now: datetime
    ) -> list[Subscription]:
        return []

    async def find_by_transaction(self, transaction_id: TransactionId) -> Subscription | None:
        return None

    async def update(self, grant: Subscription) -> None: ...


@dataclass
class FakeAcquisitionRepo:
    rows: list[Acquisition] = field(default_factory=list)

    async def add(self, acquisition: Acquisition) -> None:
        self.rows.append(acquisition)

    async def get_for(self, user_id: UserId) -> Acquisition | None:
        return next((a for a in self.rows if a.user_id == user_id), None)


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
    subs: FakeSubscriptionRepo | None = None,
    acquisitions: FakeAcquisitionRepo | None = None,
) -> tuple[RegisterUserUseCase, FakeUserRepository, FakeReferralRepo, FakeUoW]:
    users = users or FakeUserRepository()
    referrals = referrals or FakeReferralRepo()
    uow = uow or FakeUoW()
    subs = subs or FakeSubscriptionRepo()
    acquisitions = acquisitions or FakeAcquisitionRepo()
    return (
        RegisterUserUseCase(
            user_repo=users,
            referral_repo=referrals,
            subscription_repo=subs,
            acquisition_repo=acquisitions,
            uow=uow,
        ),
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


async def test_new_user_gets_welcome_premium_bonus() -> None:
    subs = FakeSubscriptionRepo()
    use_case, _, _, _ = _make_use_case(subs=subs)

    response = await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert len(subs.grants) == 1
    grant = subs.grants[0]
    assert grant.owner_id == UserId(response.id)
    assert grant.source is SubscriptionSource.BONUS
    assert grant.tier is Tier.BONUS
    assert (grant.expires_at - grant.starts_at).days == WELCOME_BONUS_DAYS
    assert grant.is_active_at(grant.starts_at) is True


async def test_returning_user_does_not_get_a_second_bonus() -> None:
    subs = FakeSubscriptionRepo()
    use_case, _, _, _ = _make_use_case(subs=subs)

    await use_case.execute(RegisterUserRequest(telegram_id=12345))
    await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert len(subs.grants) == 1


async def test_register_stores_username_stripped_of_at_sign() -> None:
    use_case, repo, _, _ = _make_use_case()

    await use_case.execute(RegisterUserRequest(telegram_id=12345, username="@anna_k"))

    assert next(iter(repo.users.values())).username == "anna_k"


async def test_returning_user_gets_username_refreshed() -> None:
    use_case, repo, _, uow = _make_use_case()
    await use_case.execute(RegisterUserRequest(telegram_id=12345, username="old_handle"))
    uow.committed = False

    await use_case.execute(RegisterUserRequest(telegram_id=12345, username="new_handle"))

    assert next(iter(repo.users.values())).username == "new_handle"
    assert uow.committed is True


async def test_returning_user_without_username_keeps_stored_one() -> None:
    """`username=None` means "caller doesn't know it" — never wipes the cached value."""
    use_case, repo, _, uow = _make_use_case()
    await use_case.execute(RegisterUserRequest(telegram_id=12345, username="anna_k"))
    uow.committed = False

    await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert next(iter(repo.users.values())).username == "anna_k"
    assert uow.committed is False  # unchanged → no pointless write


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


async def test_source_tag_is_recorded_on_registration() -> None:
    acq = FakeAcquisitionRepo()
    use_case, _, _, _ = _make_use_case(acquisitions=acq)

    response = await use_case.execute(
        RegisterUserRequest(telegram_id=12345, acquisition_source="Habr")
    )

    assert len(acq.rows) == 1
    assert acq.rows[0].user_id == UserId(response.id)
    assert acq.rows[0].source.value == "habr"  # lowercased by the VO


async def test_source_is_not_rewritten_for_returning_user() -> None:
    """Attribution means "where they came from", not "where they last came from"."""
    acq = FakeAcquisitionRepo()
    use_case, _, _, _ = _make_use_case(acquisitions=acq)

    await use_case.execute(RegisterUserRequest(telegram_id=12345, acquisition_source="habr"))
    await use_case.execute(RegisterUserRequest(telegram_id=12345, acquisition_source="tiktok"))

    assert len(acq.rows) == 1
    assert acq.rows[0].source.value == "habr"


async def test_no_payload_records_no_source() -> None:
    """Organic arrivals stay unattributed — a missing row reads as organic."""
    acq = FakeAcquisitionRepo()
    use_case, _, _, _ = _make_use_case(acquisitions=acq)

    await use_case.execute(RegisterUserRequest(telegram_id=12345))

    assert acq.rows == []


async def test_referral_arrival_records_no_separate_acquisition() -> None:
    """The referral IS the attribution: it lands in the same acquisition
    tables via the referral repository, so recording a second acquisition
    row here would violate the one-source-per-user PK."""
    acq = FakeAcquisitionRepo()
    use_case, repo, referrals, _ = _make_use_case(acquisitions=acq)
    inviter = _seed_user(repo, 111)

    await use_case.execute(
        RegisterUserRequest(
            telegram_id=12345,
            referrer_telegram_id=inviter.telegram_id.value,
        )
    )

    assert acq.rows == []
    assert len(referrals.referrals) == 1


async def test_unknown_referrer_records_no_source() -> None:
    """No Referral row means no referral channel to credit."""
    acq = FakeAcquisitionRepo()
    use_case, _, _, _ = _make_use_case(acquisitions=acq)

    await use_case.execute(RegisterUserRequest(telegram_id=12345, referrer_telegram_id=999999999))

    assert acq.rows == []


async def test_malformed_source_is_dropped_without_failing_registration() -> None:
    acq = FakeAcquisitionRepo()
    use_case, repo, _, _ = _make_use_case(acquisitions=acq)

    response = await use_case.execute(
        RegisterUserRequest(telegram_id=12345, acquisition_source="not a valid tag!")
    )

    assert response.telegram_id == 12345
    assert len(repo.users) == 1
    assert acq.rows == []


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

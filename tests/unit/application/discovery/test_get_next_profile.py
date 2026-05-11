from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.application.discovery.get_next_profile import GetNextProfileForRatingUseCase
from src.domain.discovery.repositories import DiscoveryMatch
from src.domain.discovery.specifications import (
    ProfileAverageRatingAtLeast,
    ProfileOwnerNotIn,
)
from src.domain.profile.entities import Profile
from src.domain.profile.value_objects import (
    Age,
    Bio,
    Gender,
    Location,
    Name,
    PhotoFileId,
    Photos,
    ProfileId,
)
from src.domain.shared.identifiers import UserId
from src.domain.shared.specifications import AndSpec, Specification
from src.domain.subscription.entities import Subscription
from src.domain.subscription.value_objects import Tier


@dataclass
class FakeDiscoveryRepository:
    next_profile: Profile | None = None
    last_spec: Specification | None = None
    last_viewer_location: Location | None = None

    async def find_next(
        self,
        spec: Specification,
        viewer_location: Location,
    ) -> DiscoveryMatch | None:
        self.last_spec = spec
        self.last_viewer_location = viewer_location
        if self.next_profile is None:
            return None
        return DiscoveryMatch(profile=self.next_profile, distance_meters=0)


@dataclass
class FakeProfileRepository:
    profile: Profile | None = None

    async def add(self, profile: Profile) -> None:
        self.profile = profile

    async def get_by_id(self, profile_id: ProfileId) -> Profile | None:
        return self.profile

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None:
        return self.profile

    async def exists_for_owner(self, owner_id: UserId) -> bool:
        return self.profile is not None

    async def update(self, profile: Profile) -> None:
        self.profile = profile


@dataclass
class FakeSubscriptionRepository:
    subscription: Subscription | None = None

    async def add(self, sub: Subscription) -> None:
        self.subscription = sub

    async def get_for(self, owner_id: UserId) -> Subscription | None:
        return self.subscription

    async def update(self, sub: Subscription) -> None:
        self.subscription = sub


@dataclass
class FakeSkipRegistry:
    skipped: list[UserId] = field(default_factory=list)

    async def record_skip(self, viewer_id: UserId, skipped_owner_id: UserId) -> None:
        self.skipped.append(skipped_owner_id)

    async def get_skipped(self, viewer_id: UserId) -> list[UserId]:
        return list(self.skipped)


def _make_profile() -> Profile:
    return Profile.create(
        owner_id=UserId.new(),
        name=Name("Vasya"),
        age=Age(25),
        gender=Gender.MALE,
        bio=Bio("hi"),
        photos=Photos(items=(PhotoFileId("file-id"),)),
        location=Location(lat=55.7558, lon=37.6173),
        now=datetime.now(UTC),
    )


def _make_use_case(
    discovery: FakeDiscoveryRepository,
    subs: FakeSubscriptionRepository,
    skips: FakeSkipRegistry,
    profiles: FakeProfileRepository | None = None,
) -> GetNextProfileForRatingUseCase:
    # Use case requires viewer to have a profile (with location). Tests that
    # don't care about the viewer profile still need one mounted on the repo.
    if profiles is None:
        profiles = FakeProfileRepository(profile=_make_profile())
    return GetNextProfileForRatingUseCase(
        discovery_repo=discovery,
        profile_repo=profiles,
        subscription_repo=subs,
        skip_registry=skips,
    )


def _find_spec[T: Specification](spec: Specification, kind: type[T]) -> T | None:
    if isinstance(spec, kind):
        return spec
    if isinstance(spec, AndSpec):
        for s in spec.specs:
            found = _find_spec(s, kind)
            if found is not None:
                return found
    return None


async def test_returns_response_when_candidate_exists() -> None:
    profile = _make_profile()
    use_case = _make_use_case(
        FakeDiscoveryRepository(next_profile=profile),
        FakeSubscriptionRepository(),
        FakeSkipRegistry(),
    )

    response = await use_case.execute(uuid4())

    assert response is not None
    assert response.profile_id == profile.id.value
    assert response.name == "Vasya"


async def test_returns_none_when_no_candidate() -> None:
    use_case = _make_use_case(
        FakeDiscoveryRepository(next_profile=None),
        FakeSubscriptionRepository(),
        FakeSkipRegistry(),
    )

    assert await use_case.execute(uuid4()) is None


async def test_no_subscription_omits_threshold_spec() -> None:
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(), FakeSkipRegistry()
    )

    await use_case.execute(uuid4())

    assert discovery.last_spec is not None
    assert _find_spec(discovery.last_spec, ProfileAverageRatingAtLeast) is None


async def test_active_silver_adds_threshold_7_spec() -> None:
    viewer_id = uuid4()
    sub = Subscription.activate(
        UserId(viewer_id), Tier.SILVER, duration_days=30, now=datetime.now(UTC)
    )
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(subscription=sub), FakeSkipRegistry()
    )

    await use_case.execute(viewer_id)

    assert discovery.last_spec is not None
    threshold_spec = _find_spec(discovery.last_spec, ProfileAverageRatingAtLeast)
    assert threshold_spec is not None
    assert threshold_spec.threshold == 7.0


async def test_active_gold_adds_threshold_8_spec() -> None:
    viewer_id = uuid4()
    sub = Subscription.activate(
        UserId(viewer_id), Tier.GOLD, duration_days=30, now=datetime.now(UTC)
    )
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(subscription=sub), FakeSkipRegistry()
    )

    await use_case.execute(viewer_id)

    assert discovery.last_spec is not None
    threshold_spec = _find_spec(discovery.last_spec, ProfileAverageRatingAtLeast)
    assert threshold_spec is not None
    assert threshold_spec.threshold == 8.0


async def test_expired_subscription_omits_threshold_spec() -> None:
    viewer_id = uuid4()
    sub = Subscription.activate(
        UserId(viewer_id),
        Tier.SILVER,
        duration_days=30,
        now=datetime.now(UTC) - timedelta(days=60),
    )
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(subscription=sub), FakeSkipRegistry()
    )

    await use_case.execute(viewer_id)

    assert discovery.last_spec is not None
    assert _find_spec(discovery.last_spec, ProfileAverageRatingAtLeast) is None


async def test_revoked_subscription_omits_threshold_spec() -> None:
    viewer_id = uuid4()
    sub = Subscription.activate(
        UserId(viewer_id), Tier.GOLD, duration_days=30, now=datetime.now(UTC)
    )
    sub.revoke(now=datetime.now(UTC))
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(subscription=sub), FakeSkipRegistry()
    )

    await use_case.execute(viewer_id)

    assert discovery.last_spec is not None
    assert _find_spec(discovery.last_spec, ProfileAverageRatingAtLeast) is None


async def test_no_skipped_omits_exclude_spec() -> None:
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery, FakeSubscriptionRepository(), FakeSkipRegistry(skipped=[])
    )

    await use_case.execute(uuid4())

    assert discovery.last_spec is not None
    assert _find_spec(discovery.last_spec, ProfileOwnerNotIn) is None


async def test_skipped_ids_become_owner_not_in_spec() -> None:
    skipped_a = UserId.new()
    skipped_b = UserId.new()
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    skips = FakeSkipRegistry(skipped=[skipped_a, skipped_b])
    use_case = _make_use_case(discovery, FakeSubscriptionRepository(), skips)

    await use_case.execute(uuid4())

    assert discovery.last_spec is not None
    exclude_spec = _find_spec(discovery.last_spec, ProfileOwnerNotIn)
    assert exclude_spec is not None
    assert set(exclude_spec.user_ids) == {skipped_a, skipped_b}


async def test_viewer_location_is_passed_to_repository() -> None:
    viewer_profile = _make_profile()
    viewer_profile.location = Location(lat=12.34, lon=56.78)
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    profiles = FakeProfileRepository(profile=viewer_profile)
    use_case = _make_use_case(
        discovery,
        FakeSubscriptionRepository(),
        FakeSkipRegistry(),
        profiles=profiles,
    )

    await use_case.execute(uuid4())

    assert discovery.last_viewer_location is not None
    assert discovery.last_viewer_location.lat == 12.34
    assert discovery.last_viewer_location.lon == 56.78


async def test_returns_none_when_viewer_has_no_profile() -> None:
    discovery = FakeDiscoveryRepository(next_profile=_make_profile())
    use_case = _make_use_case(
        discovery,
        FakeSubscriptionRepository(),
        FakeSkipRegistry(),
        profiles=FakeProfileRepository(profile=None),
    )

    assert await use_case.execute(uuid4()) is None

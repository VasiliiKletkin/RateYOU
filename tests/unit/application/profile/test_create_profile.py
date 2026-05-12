from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.dto import CreateProfileRequest
from src.domain.profile.entities import Profile
from src.domain.profile.exceptions import ProfileAlreadyExists
from src.domain.profile.value_objects import ProfileId
from src.domain.shared.identifiers import UserId


@dataclass
class FakeProfileRepository:
    profiles: dict[UUID, Profile] = field(default_factory=dict)

    async def add(self, profile: Profile) -> None:
        self.profiles[profile.id.value] = profile

    async def get_by_id(self, profile_id: ProfileId) -> Profile | None:
        return self.profiles.get(profile_id.value)

    async def get_by_owner_id(self, owner_id: UserId) -> Profile | None:
        for p in self.profiles.values():
            if p.owner_id == owner_id:
                return p
        return None

    async def exists_for_owner(self, owner_id: UserId) -> bool:
        return any(p.owner_id == owner_id for p in self.profiles.values())

    async def update(self, profile: Profile) -> None:
        self.profiles[profile.id.value] = profile


@dataclass
class FakeUoW:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_request(owner_id: UUID) -> CreateProfileRequest:
    return CreateProfileRequest(
        owner_id=owner_id,
        name="Vasya",
        age=25,
        gender="male",
        bio="hi",
        photo_file_ids=("file-id-1",),
        location=(55.7558, 37.6173),
    )


async def test_create_persists_profile_and_commits() -> None:
    repo = FakeProfileRepository()
    uow = FakeUoW()
    use_case = CreateProfileUseCase(profile_repo=repo, uow=uow)
    owner = uuid4()

    response = await use_case.execute(_make_request(owner))

    assert response.owner_id == owner
    assert response.name == "Vasya"
    assert response.is_visible is True
    assert uow.committed is True
    assert len(repo.profiles) == 1


async def test_create_raises_when_profile_exists_for_owner() -> None:
    repo = FakeProfileRepository()
    uow = FakeUoW()
    use_case = CreateProfileUseCase(profile_repo=repo, uow=uow)
    owner = uuid4()

    await use_case.execute(_make_request(owner))
    uow.committed = False

    with pytest.raises(ProfileAlreadyExists):
        await use_case.execute(_make_request(owner))

    assert uow.committed is False

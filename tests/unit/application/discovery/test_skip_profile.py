from dataclasses import dataclass, field
from uuid import uuid4

from src.application.discovery.skip_profile import SkipProfileUseCase
from src.domain.shared.identifiers import UserId


@dataclass
class FakeSkipRegistry:
    records: list[tuple[UserId, UserId]] = field(default_factory=list)

    async def record_skip(self, viewer_id: UserId, skipped_owner_id: UserId) -> None:
        self.records.append((viewer_id, skipped_owner_id))

    async def get_skipped(self, viewer_id: UserId) -> list[UserId]:
        return [skipped for v, skipped in self.records if v == viewer_id]


async def test_skip_records_pair_in_registry() -> None:
    registry = FakeSkipRegistry()
    use_case = SkipProfileUseCase(skip_registry=registry)
    viewer = uuid4()
    skipped = uuid4()

    await use_case.execute(viewer_id=viewer, skipped_owner_id=skipped)

    assert len(registry.records) == 1
    v, s = registry.records[0]
    assert v.value == viewer
    assert s.value == skipped


async def test_skip_records_multiple_entries() -> None:
    registry = FakeSkipRegistry()
    use_case = SkipProfileUseCase(skip_registry=registry)
    viewer = uuid4()

    await use_case.execute(viewer_id=viewer, skipped_owner_id=uuid4())
    await use_case.execute(viewer_id=viewer, skipped_owner_id=uuid4())
    await use_case.execute(viewer_id=viewer, skipped_owner_id=uuid4())

    assert len(registry.records) == 3

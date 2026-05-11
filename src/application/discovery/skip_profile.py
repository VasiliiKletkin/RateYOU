from dataclasses import dataclass
from uuid import UUID

from src.domain.discovery.skip_registry import ISkipRegistry
from src.domain.shared.identifiers import UserId


@dataclass
class SkipProfileUseCase:
    """Records that the viewer skipped a profile without rating it.

    The skipped profile will not surface again in the viewer's feed until
    the SkipRegistry's TTL elapses. No DB write, no UoW — Redis is its own
    state.
    """

    skip_registry: ISkipRegistry

    async def execute(
        self,
        viewer_id: UUID,
        skipped_owner_id: UUID,
    ) -> None:
        await self.skip_registry.record_skip(
            UserId(viewer_id),
            UserId(skipped_owner_id),
        )

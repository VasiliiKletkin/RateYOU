from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ReferralId:
    value: UUID

    @classmethod
    def new(cls) -> "ReferralId":
        return cls(uuid4())

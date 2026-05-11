from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class UserId:
    """Cross-context identifier for a User aggregate.

    Lives in the shared kernel because Profile, Rating, Subscription, Payment
    and Discovery all reference it. Only the type is shared — the User
    aggregate itself stays inside the Identity context.
    """

    value: UUID

    @classmethod
    def new(cls) -> "UserId":
        return cls(uuid4())

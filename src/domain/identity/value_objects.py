from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class TelegramId:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Telegram ID must be positive, got {self.value}")


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"

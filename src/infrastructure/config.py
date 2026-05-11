from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOT_", env_file=".env", extra="ignore")

    token: SecretStr
    use_webhook: bool = False
    webhook_base_url: str | None = None
    webhook_secret: SecretStr | None = None


class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    db: str
    user: str
    password: SecretStr

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class AdminConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", env_file=".env", extra="ignore")

    username: str = "admin"
    password: SecretStr
    secret_key: SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = Environment.DEV
    log_level: LogLevel = LogLevel.DEBUG

    bot: BotConfig = Field(default_factory=BotConfig)  # type: ignore[arg-type]
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore[arg-type]
    redis: RedisConfig = Field(default_factory=RedisConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)  # type: ignore[arg-type]


@lru_cache
def get_settings() -> Settings:
    return Settings()

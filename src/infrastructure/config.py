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

    # Default TTLs (seconds) for every Redis-backed feature. Keeps the keyspace
    # bounded: abandoned FSM sessions, throttle markers and skip sets all expire.
    fsm_state_ttl_seconds: int = 86400  # 24h — covers long onboarding/profile flows
    fsm_data_ttl_seconds: int = 86400
    throttle_ttl_seconds: int = 1
    skip_ttl_seconds: int = 3600  # 1h cooldown before a skipped profile may resurface

    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class AdminConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", env_file=".env", extra="ignore")

    username: str = "admin"
    password: SecretStr
    secret_key: SecretStr


class GeocodingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEOCODING_", env_file=".env", extra="ignore")

    base_url: str = "https://nominatim.openstreetmap.org/search"
    # Nominatim's usage policy requires a User-Agent identifying the app and
    # a way to reach its operator; requests without one get blocked.
    user_agent: str = "RateYouBot (https://github.com/VasiliiKletkin/RateYOU)"
    timeout_seconds: float = 5.0
    # Hits are cached long — city coordinates don't move. Misses expire fast
    # so a typo today doesn't poison the result for a month.
    cache_ttl_seconds: int = 30 * 24 * 3600
    cache_miss_ttl_seconds: int = 3600


class SentryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTRY_", env_file=".env", extra="ignore")

    dsn: SecretStr | None = None
    traces_sample_rate: float = 0.1


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = Environment.DEV
    log_level: LogLevel = LogLevel.DEBUG

    bot: BotConfig = Field(default_factory=BotConfig)  # type: ignore[arg-type]
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore[arg-type]
    redis: RedisConfig = Field(default_factory=RedisConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)  # type: ignore[arg-type]
    sentry: SentryConfig = Field(default_factory=SentryConfig)
    geocoding: GeocodingConfig = Field(default_factory=GeocodingConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()

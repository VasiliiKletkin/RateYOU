import logging

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.infrastructure.config import Environment, Settings

log = logging.getLogger(__name__)


def init_sentry(settings: Settings, component: str) -> None:
    """Initialize Sentry SDK. No-op if SENTRY_DSN is not set."""
    if settings.sentry.dsn is None:
        log.info("Sentry DSN not set, skipping init (component=%s)", component)
        return

    sentry_sdk.init(
        dsn=settings.sentry.dsn.get_secret_value(),
        environment=settings.environment.value,
        traces_sample_rate=(
            1.0 if settings.environment is Environment.DEV else settings.sentry.traces_sample_rate
        ),
        send_default_pii=False,
        integrations=[
            AsyncioIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
            StarletteIntegration(),
        ],
    )
    sentry_sdk.set_tag("component", component)
    log.info("Sentry initialized (component=%s, env=%s)", component, settings.environment.value)

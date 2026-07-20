import logging

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.infrastructure.config import Environment, Settings

log = logging.getLogger(__name__)


def init_sentry(settings: Settings, component: str) -> None:
    """Initialize Sentry SDK. No-op in dev, or if SENTRY_DSN is not set."""
    if settings.environment is Environment.DEV or settings.sentry.dsn is None:
        log.info(f"Sentry disabled (component={component}, env={settings.environment.value})")
        return

    sentry_sdk.init(
        dsn=settings.sentry.dsn.get_secret_value(),
        environment=settings.environment.value,
        traces_sample_rate=settings.sentry.traces_sample_rate,
        send_default_pii=False,
        integrations=[
            AsyncioIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
            StarletteIntegration(),
        ],
    )
    sentry_sdk.set_tag("component", component)
    log.info(f"Sentry initialized (component={component}, env={settings.environment.value})")

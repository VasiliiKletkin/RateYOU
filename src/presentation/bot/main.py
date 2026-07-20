import asyncio
import logging

import sentry_sdk
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import ErrorEvent
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dishka import make_async_container
from dishka.integrations.aiogram import setup_dishka
from redis.asyncio import Redis

from src.infrastructure.config import Settings, get_settings
from src.infrastructure.observability import init_sentry
from src.presentation.bot.commands import register_commands
from src.presentation.bot.handlers import all_routers
from src.presentation.bot.i18n import UserLanguageI18nMiddleware, i18n
from src.presentation.bot.middlewares import BanCheckMiddleware, ThrottlingMiddleware
from src.presentation.di import all_providers

log = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
WEBHOOK_PORT = 8080


def _register_middlewares(
    dp: Dispatcher,
    redis: Redis,
    settings: Settings,
) -> None:
    """Throttling first (cheap Redis SET NX), then ban-check (DB lookup)."""
    throttling = ThrottlingMiddleware(
        redis=redis,
        ttl_seconds=settings.redis.throttle_ttl_seconds,
    )
    ban_check = BanCheckMiddleware()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(throttling)
        observer.middleware(ban_check)


def _register_error_handler(dp: Dispatcher) -> None:
    @dp.errors()
    async def _on_error(event: ErrorEvent) -> None:
        log.exception(f"Unhandled error in update {event.update.update_id}")
        sentry_sdk.capture_exception(event.exception)


async def _run_polling(bot: Bot, dp: Dispatcher) -> None:
    log.info("Bot starting in polling mode")
    await dp.start_polling(bot)


async def _run_webhook(bot: Bot, dp: Dispatcher, settings: Settings) -> None:
    if not settings.bot.webhook_base_url:
        raise RuntimeError("BOT_USE_WEBHOOK is true but BOT_WEBHOOK_BASE_URL is empty")

    secret = (
        settings.bot.webhook_secret.get_secret_value()
        if settings.bot.webhook_secret is not None
        else None
    )

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=secret,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    await bot.set_webhook(
        url=f"{settings.bot.webhook_base_url}{WEBHOOK_PATH}",
        secret_token=secret,
        drop_pending_updates=True,
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT)
    await site.start()
    log.info(f"Bot starting in webhook mode on :{WEBHOOK_PORT}{WEBHOOK_PATH}")

    try:
        await asyncio.Event().wait()  # block forever; SIGTERM cancels
    finally:
        await bot.delete_webhook()
        await runner.cleanup()


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.value)
    init_sentry(settings, component="bot")

    container = make_async_container(*all_providers())

    bot = await container.get(Bot)
    storage = await container.get(BaseStorage)
    redis = await container.get(Redis)

    dp = Dispatcher(storage=storage)
    for router in all_routers():
        dp.include_router(router)

    setup_dishka(container=container, router=dp, auto_inject=True)
    _register_middlewares(dp, redis, settings)
    _register_error_handler(dp)
    UserLanguageI18nMiddleware(i18n).setup(dp)
    await register_commands(bot, i18n)

    try:
        if settings.bot.use_webhook:
            await _run_webhook(bot, dp, settings)
        else:
            await _run_polling(bot, dp)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
